"""Operators for MoGe Splat Studio: scanning, relighting, levelling, and camera controls."""
from __future__ import annotations

import os
import io
import json
import math
import mimetypes
from pathlib import Path

import bpy
import numpy as np
from bpy.types import Operator
from mathutils import Vector, Matrix

from .network import (
    daemon_get,
    daemon_post_multipart,
    daemon_health,
    daemon_stop,
    ensure_daemon_ready,
)
from .cleanup import (
    prepare_new_scan_cache,
    purge_orphaned_blender_datablocks,
    get_active_scan_dir,
    MOGE_OT_purge_all_cache,
)
from .nodes import new_splat_object, set_splat_radius_all, setup_compositor_relighter
from .preferences import get_preferences

LEVEL_EMPTY = "MoGe_Level"
LEVEL_MARKERS = ("MoGe_Floor_A", "MoGe_Floor_B", "MoGe_Floor_C")
POINT_SCALE = 1.4
R_MIN = 0.001
R_MAX = 0.06


def fov_y_from_fov_x(fov_x_deg: float, w: int, h: int) -> float:
    fx = math.radians(float(fov_x_deg))
    fy = 2.0 * math.atan(math.tan(fx / 2.0) * (float(h) / float(w)))
    return math.degrees(fy)


def _infer_to_orig_coords(xs, ys, w: int, h: int, w0: int, h0: int):
    xs = np.asarray(xs)
    ys = np.asarray(ys)
    if w0 == w and h0 == h:
        return xs, ys
    rx = float(w0) / float(w)
    ry = float(h0) / float(h)
    xo = np.clip(np.rint(xs.astype(np.float64) * rx), 0, w0 - 1).astype(np.int64)
    yo = np.clip(np.rint(ys.astype(np.float64) * ry), 0, h0 - 1).astype(np.int64)
    return xo, yo


def _load_native_rgb(path: str):
    try:
        from PIL import Image as PILImage
        with PILImage.open(path) as im:
            im = im.convert("RGB")
            return np.asarray(im, dtype=np.uint8)
    except Exception:
        pass
    img = bpy.data.images.load(path, check_existing=False)
    try:
        w, h = int(img.size[0]), int(img.size[1])
        px = np.empty(w * h * 4, dtype=np.float32)
        img.pixels.foreach_get(px)
        px = px.reshape(h, w, 4)
        px = px[::-1, :, :3]
        return (np.clip(px, 0.0, 1.0) * 255.0).astype(np.uint8)
    finally:
        try:
            bpy.data.images.remove(img)
        except Exception:
            pass


def _save_rgb_to_png(arr_rgb: np.ndarray, path: Path):
    """Save RGB uint8 array to PNG using PIL if available, else native Blender images."""
    try:
        from PIL import Image as PILImage
        PILImage.fromarray(arr_rgb).save(path)
        return
    except Exception:
        pass

    h, w = arr_rgb.shape[:2]
    img = bpy.data.images.new("temp_export", width=w, height=h, alpha=False, float_buffer=False)
    try:
        rgba = np.empty((h, w, 4), dtype=np.float32)
        rgba[..., :3] = arr_rgb.astype(np.float32) / 255.0
        rgba[..., 3] = 1.0
        rgba = rgba[::-1, :, :]  # Bottom-to-top orientation for Blender
        img.pixels.foreach_set(rgba.ravel())
        img.filepath_raw = str(path)
        img.file_format = 'PNG'
        img.save()
    finally:
        try:
            bpy.data.images.remove(img)
        except Exception:
            pass


class MOGE_OT_ensure_daemon(Operator):
    bl_idname = "moge_splat.ensure_daemon"
    bl_label = "Check AI Engine"
    bl_description = "Verify that the local GPU AI engine is running and check VRAM usage"
    bl_options = {'REGISTER'}

    def execute(self, context):
        state, payload = daemon_health()
        if state == "ok":
            models = ",".join(payload.get("models_loaded", [])) or "warming"
            mem = f"VRAM: {payload.get('gpu_allocated_gb', 0):.1f} GB allocated"
            self.report({'INFO'}, f"AI Engine OK ({state}) | Models: {models} | {mem}")
        elif state == "refused":
            self.report({'WARNING'}, f"AI engine is not running. Hit Generate to auto-start or run launch_daemon.bat.")
        else:
            self.report({'ERROR'}, f"AI engine status: {state} ({payload})")
        return {'FINISHED'}


class MOGE_OT_stop_daemon(Operator):
    bl_idname = "moge_splat.stop_daemon"
    bl_label = "Stop AI Engine"
    bl_description = "Stop the local GPU AI engine and release GPU VRAM"
    bl_options = {'REGISTER'}

    def execute(self, context):
        ok, msg = daemon_stop()
        if ok:
            self.report({'INFO'}, msg)
        else:
            self.report({'WARNING'}, msg)
        return {'FINISHED'}


class MOGE_OT_scan_splat_daemon(Operator):
    bl_idname = "moge_splat.scan_daemon"
    bl_label = "Generate 3D Splats"
    bl_description = "Run AI depth inference and generate 3D point splats in Blender"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        props = context.scene.moge_splat_props
        target_path = bpy.path.abspath(props.import_path)
        if not target_path or not os.path.exists(target_path):
            self.report({'ERROR'}, "Select a valid image file first.")
            return {'CANCELLED'}

        ext = os.path.splitext(target_path)[1].lower()
        if ext not in ('.jpg', '.jpeg', '.png', '.webp', '.bmp', '.tiff'):
            self.report({'ERROR'}, f"Unsupported image format: {ext}")
            return {'CANCELLED'}

        # Surface mode mappings
        if props.surface_mode == 'SEAMLESS':
            seamless, apply_mask, remove_edges = True, False, False
        elif props.surface_mode == 'MASKED':
            seamless, apply_mask, remove_edges = False, True, False
        else:
            seamless, apply_mask, remove_edges = False, bool(props.apply_mask), True

        ready, msg = ensure_daemon_ready(props, autostart=bool(props.daemon_autostart))
        if not ready:
            self.report({'ERROR'}, msg)
            return {'CANCELLED'}

        try:
            with open(target_path, "rb") as f:
                img_bytes = f.read()
        except Exception as e:
            self.report({'ERROR'}, f"Cannot read image: {e}")
            return {'CANCELLED'}

        mime, _ = mimetypes.guess_type(target_path)
        mime = mime or "image/jpeg"

        fields = {
            "model_version": props.model_version,
            "variant": getattr(props, "model_variant", "vitl") or "vitl",
            "resolution_level": props.resolution_level,
            "refine_steps": str(props.refine_steps),
            "max_size": str(props.max_size),
            "seamless": "true" if seamless else "false",
            "apply_mask": "true" if apply_mask else "false",
            "remove_edges": "true" if remove_edges else "false",
            "tta": getattr(props, "tta_mode", "off") or "off",
        }
        if props.use_custom_fov and props.custom_fov > 1.0:
            fields["fov_x_override"] = str(props.custom_fov)

        self.report({'INFO'}, f"Inferring {props.model_version}/{getattr(props, 'model_variant', 'vitl')} ...")
        try:
            scode, ctype, payload = daemon_post_multipart(
                "/infer", fields, "image", os.path.basename(target_path), img_bytes, mime, timeout=180.0
            )
        except Exception as e:
            self.report({'ERROR'}, f"Daemon request failed: {e}")
            return {'CANCELLED'}

        if scode != 200:
            try:
                err = json.loads(payload.decode("utf-8", "replace")).get("error", payload[:300])
            except Exception:
                err = payload[:300]
            self.report({'ERROR'}, f"Daemon error ({scode}): {err}")
            return {'CANCELLED'}

        # Decode .npz payload
        try:
            z = np.load(io.BytesIO(payload), allow_pickle=False)
            points = np.asarray(z["points"], dtype=np.float32)
            depth = np.asarray(z["depth"], dtype=np.float32)
            normal = np.asarray(z["normal"], dtype=np.float32)
            mask = np.asarray(z["mask"]).astype(bool)
            K = np.asarray(z["intrinsics"], dtype=np.float32)
            img_rgb = np.asarray(z["image"])
            fov_x = float(z["fov_x"])
            fov_y = float(z["fov_y"])
            W, H = int(z["width"]), int(z["height"])
            W0, H0 = int(z.get("orig_width", W)), int(z.get("orig_height", H))
            fov_src = str(z.get("fov_src", "model"))
            tta_used = str(z.get("tta", "off"))
        except Exception as e:
            self.report({'ERROR'}, f"Failed to decode response: {e}")
            return {'CANCELLED'}

        valid = mask & np.isfinite(depth) & (depth >= 0.08) & np.all(np.isfinite(points), axis=-1)
        if normal is not None and getattr(normal, 'shape', None) and normal.shape[:2] == depth.shape:
            valid = valid & np.all(np.isfinite(normal), axis=-1)
        ys, xs = np.nonzero(valid)
        n_all = int(valid.sum())
        if n_all < 100:
            self.report({'ERROR'}, "Too few valid points returned. Try 'Seamless' mode.")
            return {'CANCELLED'}

        stride = 1
        effective_budget = props.point_budget
        if props.splat_style == 'SURFELS':
            # Safeguard: Each surfel instantiates a 6-sided polygon.
            # Clamp surfels to 500k to prevent realizing >3M polygons and freezing the viewport depsgraph.
            effective_budget = min(effective_budget, 500_000)

        if n_all > effective_budget:
            stride = int(math.ceil(n_all / float(effective_budget)))
            xs = xs[::stride]
            ys = ys[::stride]
        pts = points[ys, xs]

        # Decoupled high-res color
        color_src = "infer"
        cols = None
        native = None
        if props.fullres_color and os.path.exists(target_path):
            try:
                native = _load_native_rgb(target_path)
                if native.ndim == 3 and native.shape[2] == 3:
                    H0n, W0n = int(native.shape[0]), int(native.shape[1])
                    W0, H0 = W0n, H0n
                    if W0n != W or H0n != H:
                        xo, yo = _infer_to_orig_coords(xs, ys, W, H, W0n, H0n)
                        cols = native[yo, xo].astype(np.float32) / 255.0
                        color_src = f"native {W0n}x{H0n}"
                    else:
                        color_src = "native (1:1)"
            except Exception as e:
                color_src = f"infer ({e})"
        if cols is None:
            cols = img_rgb[ys, xs].astype(np.float32) / 255.0

        pdepth = depth[ys, xs]
        min_d = float(np.percentile(pdepth, 1))
        max_d = float(np.percentile(pdepth, 99))
        fx_norm = float(K[0, 0])
        fx_px = fx_norm * W if fx_norm <= 1.0 else fx_norm

        # Adaptive radii with guaranteed physical bounds (prevents giant blobs)
        def _adaptive_radii(d, fx):
            raw = (np.maximum(d, 0.05) / max(fx, 1.0)) * POINT_SCALE * float(props.radius_scale)
            return np.clip(raw, R_MIN, R_MAX)

        radii = _adaptive_radii(pdepth, fx_px)
        radius_fallback = float(np.median(radii)) if len(radii) else 0.01
        radius_src = f"adaptive x{float(props.radius_scale):.2f} med {radius_fallback * 1000.0:.1f}mm"

        # --- Self-Cleaning: Wipe previous temporary scan files ---
        cache_dir = prepare_new_scan_cache()

        try:
            (cache_dir / "response.npz").write_bytes(payload)
            meta = {
                "image_file": os.path.basename(target_path),
                "fov_x": fov_x, "fov_y": fov_y, "fov_src": fov_src,
                "image_width": W, "image_height": H,
                "orig_width": W0, "orig_height": H0, "color_src": color_src,
                "radius_src": radius_src, "fx_px": fx_px,
                "min_depth": min_d, "max_depth": max_d,
                "model_version": props.model_version,
                "variant": getattr(props, "model_variant", "vitl") or "vitl",
                "tta": tta_used, "points": int(pts.shape[0]),
            }
            with open(cache_dir / "meta.json", "w") as f:
                json.dump(meta, f, indent=2)
        except Exception:
            pass

        props.last_scan_folder = str(cache_dir)
        props.last_scanned_image = target_path
        props.last_scan_points = int(pts.shape[0])
        props.last_scan_model = f"{props.model_version}/{getattr(props, 'model_variant', 'vitl') or 'vitl'}"
        props.last_scan_depth_range = f"{min_d:.2f}m .. {max_d:.2f}m"
        props.last_scan_fov = f"{fov_x:.1f}° × {fov_y:.1f}° ({fov_src})"
        props.cache_size_mb = round(len(payload) / (1024.0 * 1024.0), 1)

        # Cleanup old Blender objects & datablocks if configured
        prefs = get_preferences()
        auto_purge = prefs.auto_purge_datablocks if prefs else True

        for obj in list(context.scene.objects):
            if obj.name in ("MoGe_Splats", "MoGe_Camera", "MoGe_Geometry"):
                try:
                    bpy.data.objects.remove(obj, do_unlink=True)
                except Exception:
                    pass

        if auto_purge:
            purge_orphaned_blender_datablocks()

        xyz_bl = np.stack([pts[:, 0], pts[:, 2], -pts[:, 1]], axis=-1)

        norms_bl = None
        if normal is not None and getattr(normal, 'shape', None) and normal.shape[:2] == depth.shape:
            try:
                norms = normal[ys, xs]
                norms_bl = np.stack([norms[:, 0], norms[:, 2], -norms[:, 1]], axis=-1).astype(np.float32)
                n_len = np.linalg.norm(norms_bl, axis=-1, keepdims=True)
                norms_bl = np.where(n_len > 1e-6, norms_bl / np.maximum(n_len, 1e-6), np.array([0, 0, 1], dtype=np.float32))
            except Exception:
                norms_bl = None

        new_splat_object(
            context, xyz_bl, cols, pdepth, radii, fx_px,
            float(props.radius_scale), radius_fallback,
            normals=norms_bl, splat_style=props.splat_style,
            shading_mode=getattr(props, "shading_mode", "NORMAL"),
        )

        # Build Camera
        cam_data = bpy.data.cameras.new("MoGe_Camera")
        cam_obj = bpy.data.objects.new("MoGe_Camera", cam_data)
        context.collection.objects.link(cam_obj)
        cam_obj.location = (0.0, 0.0, 0.0)
        cam_obj.rotation_euler = (math.radians(90.0), 0.0, 0.0)
        cam_data.sensor_width = 36.0
        cam_data.sensor_fit = "HORIZONTAL"
        cam_data.lens = (36.0 / 2.0) / math.tan(math.radians(max(fov_x, 1.0) / 2.0))
        cam_data.clip_start = max(0.05, min_d * 0.3)
        cam_data.clip_end = max(100.0, max_d * 2.0)
        cam_data.display_size = 0.5
        cam_data.show_name = True
        cam_data.show_passepartout = True
        cam_data.passepartout_alpha = 1.0
        context.scene.camera = cam_obj

        # Match scene render resolution & aspect ratio to input photo
        if W0 > 0 and H0 > 0:
            context.scene.render.resolution_x = int(W0)
            context.scene.render.resolution_y = int(H0)
            context.scene.render.pixel_aspect_x = 1.0
            context.scene.render.pixel_aspect_y = 1.0

        self.report({'INFO'}, f"Done: {pts.shape[0]:,} splats ({radius_src}). Hit Camera or Relight.")
        return {'FINISHED'}


class MOGE_OT_update_splat_radius(Operator):
    bl_idname = "moge_splat.update_radius"
    bl_label = "Apply Splat Radius"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        props = context.scene.moge_splat_props
        obj = context.active_object
        if obj is None or "MoGe_Splat" not in obj.name:
            obj = bpy.data.objects.get("MoGe_Splats")
        if obj is None:
            self.report({'ERROR'}, "Select a MoGe Splat object first.")
            return {'CANCELLED'}

        mesh = obj.data
        u_rad = float(props.splat_radius)
        if u_rad > 0.0:
            set_splat_radius_all(u_rad)
            self.report({'INFO'}, f"Applied uniform radius {u_rad * 1000.0:.1f}mm")
            return {'FINISHED'}

        # Adaptive re-scaling
        attr_d = mesh.attributes.get("SplatDepth")
        attr_r = mesh.attributes.get("SplatRadius")
        if attr_d is None or attr_r is None:
            set_splat_radius_all(0.015)
            self.report({'WARNING'}, "Mesh lacks depth attribute; set 15mm uniform.")
            return {'FINISHED'}

        n = len(mesh.vertices)
        depths = np.empty(n, dtype=np.float32)
        attr_d.data.foreach_get("value", depths)
        fx_px = float(obj.get("moge_fx_px", 1000.0))
        scale = float(props.radius_scale)

        raw = (np.maximum(depths, 0.05) / max(fx_px, 1.0)) * POINT_SCALE * scale
        radii = np.clip(raw, R_MIN, R_MAX)
        attr_r.data.foreach_set("value", radii)
        mesh.update()
        obj["moge_radius_scale"] = scale
        med_mm = float(np.median(radii)) * 1000.0
        self.report({'INFO'}, f"Applied adaptive scale x{scale:.2f} (median {med_mm:.1f}mm)")
        return {'FINISHED'}


class MOGE_OT_view_camera(Operator):
    bl_idname = "moge_splat.view_camera"
    bl_label = "Switch to Camera View"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        cam = bpy.data.objects.get("MoGe_Camera") or context.scene.camera
        if cam is None:
            self.report({'ERROR'}, "No MoGe camera in scene.")
            return {'CANCELLED'}
        context.scene.camera = cam
        if hasattr(cam.data, "passepartout_alpha"):
            cam.data.show_passepartout = True
            cam.data.passepartout_alpha = 1.0

        for area in context.screen.areas:
            if area.type == 'VIEW_3D':
                for space in area.spaces:
                    if space.type == 'VIEW_3D':
                        space.region_3d.view_perspective = 'CAMERA'
        self.report({'INFO'}, "Active camera set to MoGe_Camera.")
        return {'FINISHED'}


class MOGE_OT_setup_compositor_relight(Operator):
    bl_idname = "moge_splat.setup_relight"
    bl_label = "Setup 2.5D Relighter"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        active_dir = get_active_scan_dir()
        img_file = active_dir / "image.png"
        norm_file = active_dir / "normal.png"
        npz_file = active_dir / "response.npz"

        if not npz_file.exists():
            self.report({'ERROR'}, "No active scan cache. Run Scan first.")
            return {'CANCELLED'}

        # Lazy export: generate image.png and normal.png on-demand if not already written
        if not img_file.exists() or not norm_file.exists():
            try:
                z = np.load(npz_file, allow_pickle=False)
                img_rgb = np.asarray(z["image"])
                normal = np.asarray(z["normal"], dtype=np.float32)
                _save_rgb_to_png(img_rgb, img_file)
                nvis = ((np.clip(normal, -1, 1) * 0.5 + 0.5) * 255.0).astype(np.uint8)
                _save_rgb_to_png(nvis, norm_file)
            except Exception as e:
                self.report({'ERROR'}, f"Failed generating preview maps: {e}")
                return {'CANCELLED'}

        ok, msg = setup_compositor_relighter(context, img_file, norm_file)
        if ok:
            # Switch to compositing workspace if present
            if "Compositing" in bpy.data.workspaces and getattr(context, "window", None):
                context.window.workspace = bpy.data.workspaces["Compositing"]
            self.report({'INFO'}, msg)
            return {'FINISHED'}
        self.report({'ERROR'}, msg)
        return {'CANCELLED'}


# --- Floor Levelling Operators ---

def _apply_level_matrix(context, M_rows, label: str):
    M = Matrix([list(map(float, row)) for row in M_rows])
    empty = bpy.data.objects.get(LEVEL_EMPTY)
    if empty is not None and empty.type != "EMPTY":
        bpy.data.objects.remove(empty, do_unlink=True)
        empty = None
    if empty is None:
        empty = bpy.data.objects.new(LEVEL_EMPTY, None)
        context.collection.objects.link(empty)
        empty.empty_display_type = "PLAIN_AXES"
    empty.matrix_world = M
    empty["moge_level_label"] = label[:200]

    for name in ("MoGe_Splats", "MoGe_Camera"):
        o = bpy.data.objects.get(name)
        if o and o != empty:
            o.parent = empty
            o.matrix_parent_inverse.identity()
    return empty


class MOGE_OT_level_auto(Operator):
    bl_idname = "moge_splat.level_auto"
    bl_label = "Align Floor (Auto)"
    bl_description = "Automatically detect the ground plane and align it flat to grid Z=0"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        props = context.scene.moge_splat_props
        npz_path = get_active_scan_dir() / "response.npz"
        if not npz_path.exists():
            self.report({'ERROR'}, "No active scan data found. Please run Scan first.")
            return {'CANCELLED'}

        try:
            raw = npz_path.read_bytes()
            scode, ctype, payload = daemon_post_multipart(
                "/level", {"ransac_iters": "1500", "cone_deg": "40.0", "seed": "0"},
                "maps", "response.npz", raw, "application/x-numpy-archive", timeout=120.0
            )
        except Exception as e:
            self.report({'ERROR'}, f"Level request failed: {e}")
            return {'CANCELLED'}

        if scode != 200:
            self.report({'ERROR'}, f"Auto-level error ({scode})")
            return {'CANCELLED'}

        try:
            res = json.loads(payload.decode("utf-8", "replace"))
            if not res.get("ok") or "matrix_blender" not in res:
                self.report({'ERROR'}, f"Leveling failed: {res.get('message', 'unknown')}")
                return {'CANCELLED'}

            empty = _apply_level_matrix(context, res["matrix_blender"], f"auto: {res.get('message', '')}")
            self.report({'INFO'}, f"Floor levelled to Z=0. Tweak via '{LEVEL_EMPTY}' Empty.")
            context.view_layer.objects.active = empty
            empty.select_set(True)
            return {'FINISHED'}
        except Exception as e:
            self.report({'ERROR'}, f"Failed to apply matrix: {e}")
            return {'CANCELLED'}


class MOGE_OT_level_markers_add(Operator):
    bl_idname = "moge_splat.level_markers_add"
    bl_label = "Add 3 Floor Markers"
    bl_description = "Spawn 3 markers in front of the camera to manually define the floor plane"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        cam = context.scene.camera
        if cam is None:
            self.report({'ERROR'}, "No camera in scene.")
            return {'CANCELLED'}
        loc = cam.matrix_world.translation.copy()
        z_axis = (cam.matrix_world @ Vector((0.0, 0.0, -1.0))) - loc
        z_axis.normalize()
        x_axis = (cam.matrix_world @ Vector((1.0, 0.0, 0.0))) - loc
        x_axis.normalize()
        y_axis = (cam.matrix_world @ Vector((0.0, 1.0, 0.0))) - loc
        y_axis.normalize()
        base = loc + z_axis * 4.0

        for name, (ox, oy) in zip(LEVEL_MARKERS, [(-0.8, -0.5), (0.8, -0.5), (0.0, 0.7)]):
            o = bpy.data.objects.get(name)
            if o is None:
                o = bpy.data.objects.new(name, None)
                context.collection.objects.link(o)
                o.empty_display_type = "SPHERE"
            o.location = base + x_axis * ox + y_axis * oy
            o.empty_display_size = 0.15
            o.show_name = True
        self.report({'INFO'}, "Position A, B, C markers on the floor and click 'Align to Markers'.")
        return {'FINISHED'}


class MOGE_OT_level_markers_apply(Operator):
    bl_idname = "moge_splat.level_markers_apply"
    bl_label = "Align to Markers"
    bl_description = "Calculate the floor plane from markers A, B, and C and rotate scene to grid Z=0"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        pts = []
        for name in LEVEL_MARKERS:
            o = bpy.data.objects.get(name)
            if not o:
                self.report({'ERROR'}, f"Marker '{name}' not found.")
                return {'CANCELLED'}
            pts.append(o.matrix_world.translation.copy())

        A = np.stack([[p.x, p.y, p.z] for p in pts], axis=0).astype(np.float64)
        c = A.mean(axis=0)
        _, _, vt = np.linalg.svd(A - c, full_matrices=False)
        n = vt[-1]
        if n[2] < 0:
            n = -n
        n = n / max(np.linalg.norm(n), 1e-12)
        d = -float(n @ c)

        R = Vector((float(n[0]), float(n[1]), float(n[2]))).rotation_difference(Vector((0.0, 0.0, 1.0))).to_matrix().to_4x4()
        T = Matrix.Translation((0.0, 0.0, float(d)))
        M = T @ R

        empty = _apply_level_matrix(context, [[float(v) for v in row] for row in M], "manual-markers")
        self.report({'INFO'}, "Levelled to markers.")
        return {'FINISHED'}


class MOGE_OT_level_remove(Operator):
    bl_idname = "moge_splat.level_remove"
    bl_label = "Reset Alignment"
    bl_description = "Remove floor alignment transformation and reset objects to raw camera coordinates"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        empty = bpy.data.objects.get(LEVEL_EMPTY)
        if empty:
            for child in list(empty.children):
                m = child.matrix_world.copy()
                child.parent = None
                child.matrix_world = m
            bpy.data.objects.remove(empty, do_unlink=True)
            self.report({'INFO'}, "Levelling removed.")
            return {'FINISHED'}
        self.report({'INFO'}, "No levelling active.")
        return {'FINISHED'}


class MOGE_OT_set_resolution(Operator):
    """Switch resolution preset long-edge dimension (1536, 2448, 4096)"""
    bl_idname = "moge_splat.set_resolution"
    bl_label = "Set Resolution"
    bl_description = "Switch resolution preset (1536 Standard, 2448 2.5K, 4096 4K)"
    bl_options = {'INTERNAL', 'UNDO'}

    resolution: bpy.props.IntProperty(name="Resolution", default=1536)

    def execute(self, context):
        props = context.scene.moge_splat_props
        props.max_size = self.resolution
        return {'FINISHED'}
