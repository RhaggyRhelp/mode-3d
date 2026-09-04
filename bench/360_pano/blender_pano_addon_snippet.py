
PANO_RIG = "MoGe_PanoRig"


# ---------------------------------------------------------------------------
# Panorama rooms: equirect -> faces -> merged cloud + yaw/pitch camera rig
# ---------------------------------------------------------------------------


def _build_pano_rig(context, yaws, pitches):
    """Camera rig for pano faces: one Empty + yaw/pitch cameras at the shared
    center, each looking along its face ray with face-up orientation.
    Returns (rig, cams). Testable without any inference."""
    from mathutils import Matrix as _M, Vector as _V
    rig = bpy.data.objects.get(PANO_RIG)
    if rig is not None:
        try:
            bpy.data.objects.remove(rig, do_unlink=True)
        except Exception:
            pass
    rig = bpy.data.objects.new(PANO_RIG, None)
    context.collection.objects.link(rig)
    rig.empty_display_type = "ARROWS"
    rig.location = (0.0, 0.0, 0.0)
    cams = []
    for i, (yw, pt) in enumerate(zip(yaws, pitches)):
        cd = bpy.data.cameras.new(f"MoGe_Pano_{i:02d}")
        cd.sensor_width = 36.0
        cd.sensor_fit = "HORIZONTAL"
        cd.lens = (36.0 / 2.0) / math.tan(math.radians(45.0))
        cd.clip_start = 0.05
        cd.clip_end = 500.0
        cd.display_size = 0.4
        for _attr, _val in (("show_passepartout", True), ("passepartout_alpha", 1.0)):
            try:
                setattr(cd, _attr, _val)
            except Exception:
                pass
        co = bpy.data.objects.new(f"MoGe_Pano_{i:02d}", cd)
        context.collection.objects.link(co)
        co.location = (0.0, 0.0, 0.0)
        # pano frame is y-DOWN (face0 CV); convert rotation to Blender:
        # R_bl = S @ R_cv, with S the CV->Blender axis map, then basis.
        t = math.radians(float(yw))
        p = math.radians(float(pt))
        # Matches shared.pano.tangent_frame (pitch>0 looks up in y-down CV).
        Rx = _M(((1, 0, 0), (0, math.cos(p), -math.sin(p)),
                 (0, math.sin(p), math.cos(p))))
        Ry = _M(((math.cos(t), 0, math.sin(t)), (0, 1, 0),
                 (-math.sin(t), 0, math.cos(t))))
        Rcv = Ry @ Rx
        fwd_cv = Rcv @ _V((0.0, 0.0, 1.0))
        up_cv = Rcv @ _V((0.0, -1.0, 0.0))
        fwd = _V((fwd_cv.x, fwd_cv.z, -fwd_cv.y))
        up = _V((up_cv.x, up_cv.z, -up_cv.y))
        # Right-handed camera basis: Z = -fwd, X = up x Z, Y = Z x X.
        # (The naive up x fwd order yields a reflection, det -1, and to_euler
        # silently returns garbage.)
        zc = (-fwd).normalized()
        xc = up.cross(zc)
        xc = xc.normalized() if xc.length > 1e-6 else _V((1.0, 0.0, 0.0))
        yc = zc.cross(xc).normalized()
        co.rotation_euler = (_M((xc, yc, zc)).transposed()).to_euler()
        co.parent = rig
        try:
            co.matrix_parent_inverse.identity()
        except Exception:
            pass
        cams.append(co)
    try:
        context.view_layer.update()
    except Exception:
        pass
    return rig, cams


class MOGE_OT_scan_pano(Operator):
    """Full-room scan: 8 side faces + poles, scale-solved, one cloud + rig"""
    bl_idname = "moge_splat.scan_pano"
    bl_label = "Scan 360 Room"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        if not _HAS_NUMPY:
            self.report({'ERROR'}, "Blender numpy missing.")
            return {'CANCELLED'}
        props = context.scene.moge_splat_props
        target_path = bpy.path.abspath(props.pano_path)
        if not target_path or not os.path.exists(target_path):
            self.report({'ERROR'}, "Pick a 360 equirect image (2:1) first.")
            return {'CANCELLED'}

        ready, msg = _ensure_daemon_ready(props, autostart=bool(props.daemon_autostart))
        if not ready:
            self.report({'ERROR'}, msg)
            return {'CANCELLED'}

        try:
            with open(target_path, "rb") as f:
                img_bytes = f.read()
        except Exception as e:
            self.report({'ERROR'}, f"Cannot read image: {e}")
            return {'CANCELLED'}
        layout_mode = getattr(props, "pano_layout", "CUBE_6") or "CUBE_6"
        if layout_mode == "CUBE_4":
            req_n_yaw = "4"
            req_poles = "false"
            num_desc = "4 cubemap walls"
        elif layout_mode == "CUBE_6":
            req_n_yaw = "4"
            req_poles = "true"
            num_desc = "6 cubemap faces"
        else:
            req_n_yaw = "8"
            req_poles = "true" if props.pano_poles else "false"
            num_desc = f"{10 if props.pano_poles else 8} legacy views"

        self.report({'INFO'}, f"{msg}; inferring {num_desc} ...")

        fields = {
            "n_yaw": req_n_yaw,
            "include_poles": req_poles,
            "face_size": str(props.pano_face_size),
            "model_version": "v3",
            "variant": getattr(props, "model_variant", "vitl") or "vitl",
            "resolution_level": props.resolution_level,
            "refine_steps": str(props.refine_steps),
            "apply_mask": "false",
            "remove_edges": "true" if props.pano_edge_cut else "false",
            "face_cap": str(props.pano_face_cap),
        }
        try:
            scode, ctype, payload = daemon_post_multipart(
                "/pano", fields, "image", os.path.basename(target_path), img_bytes,
                mimetypes.guess_type(target_path)[0] or "image/jpeg", timeout=900.0)
        except Exception as e:
            self.report({'ERROR'}, f"Pano request failed: {e}")
            return {'CANCELLED'}
        if scode != 200:
            try:
                err = json.loads(payload.decode("utf-8", "replace")).get("error", payload[:300])
            except Exception:
                err = payload[:300]
            self.report({'ERROR'}, f"Pano failed HTTP {scode}: {err}")
            return {'CANCELLED'}

        try:
            z = np.load(io.BytesIO(payload), allow_pickle=False)
            P = np.asarray(z["points"], dtype=np.float32)    # (M,3) pano frame
            C = (np.asarray(z["colors"], dtype=np.float32) / 255.0)
            N = np.asarray(z["normals"], dtype=np.float32)
            D = np.asarray(z["depths"], dtype=np.float32)
            F = np.asarray(z["face_id"]).astype(np.int32)
            yaws = [float(v) for v in np.asarray(z["face_yaw"]).tolist()]
            pitches = [float(v) for v in np.asarray(z["face_pitch"]).tolist()]
            scales = [float(v) for v in np.asarray(z["scales"]).tolist()]
            fx = float(z["fx_px"])
            pre = float(z["pre_resid"])
            post = float(z["post_resid"])
            try:
                _seam_v = float(z["seam_resid"])
                seam_s = f"{_seam_v * 100:.1f}%" if _seam_v >= 0 else "n/a"
            except Exception:
                seam_s = "n/a"
        except Exception as e:
            self.report({'ERROR'}, f"Bad pano payload: {e}")
            return {'CANCELLED'}
        m = int(P.shape[0])
        if m < 100:
            self.report({'ERROR'}, "Pano returned <100 points.")
            return {'CANCELLED'}

        # Blender coords + adaptive radii with the faces' own fx.
        xyz = np.stack([P[:, 0], P[:, 2], -P[:, 1]], axis=-1).astype(np.float32)
        finite = np.isfinite(D)
        D = np.where(finite, D, np.median(D[finite]) if finite.any() else 3.0)
        if float(props.splat_radius) > 0:
            radii = np.full(m, float(props.splat_radius), dtype=np.float32)
            radius_src = f"uniform {float(props.splat_radius) * 1000.0:.1f}mm"
        else:
            b = D.astype(np.float64) / max(fx, 1.0) * POINT_SCALE
            radii = np.clip(b * float(props.radius_scale), 0.001, 0.25).astype(np.float32)
            radius_src = (f"pano-adaptive x{float(props.radius_scale):.2f} med "
                          f"{float(np.median(radii)) * 1000.0:.1f}mm")
        radius_fallback = float(np.median(radii)) if m else 0.01
        try:
            seam = float(z["seam_resid"])
            seam_s = f"{seam * 100:.1f}%" if seam >= 0 else "n/a"
        except Exception:
            seam, seam_s = -1.0, "n/a"

        # Per-face stride plan (even budget split across present faces).
        present = sorted(set(int(v) for v in F.tolist()))
        per = max(1, int(math.ceil(float(props.point_budget) / max(len(present), 1))))
        plan = {}
        for fi in present:
            idx = np.nonzero(F == fi)[0]
            st = int(math.ceil(len(idx) / per)) if len(idx) > per else 1
            plan[fi] = idx[::st]

        stem = os.path.splitext(os.path.basename(target_path))[0]
        cache_dir = Path(tempfile.gettempdir()) / f"moge_pano_{stem}"
        shutil.rmtree(cache_dir, ignore_errors=True)
        cache_dir.mkdir(parents=True, exist_ok=True)
        try:
            (cache_dir / "pano.npz").write_bytes(payload)
            with open(cache_dir / "meta.json", "w") as f:
                json.dump({"image_file": os.path.basename(target_path),
                           "kind": "pano", "faces": len(yaws),
                           "model_version": "v3",
                           "variant": getattr(props, "model_variant", "vitl") or "vitl",
                           "scales": [round(s, 4) for s in scales],
                           "pre_resid": round(pre, 4), "post_resid": round(post, 5),
                           "seam_resid": seam_s,
                           "seam_resid": seam_s,
                           "face_counts": {str(fi): int(len(plan[fi])) for fi in present},
                           "min_depth": float(np.min(D)), "max_depth": float(np.max(D)),
                           "radius_src": radius_src,
                           "points": int(sum(len(plan[fi]) for fi in present))}, f, indent=2)
        except Exception:
            pass

        prefs_edit = context.preferences.edit
        prev_undo = prefs_edit.use_global_undo
        try:
            prefs_edit.use_global_undo = False
        except Exception:
            pass
        try:
            # Cleanup: legacy singles, previous pano faces/cams/rig/collections.
            for o in list(bpy.data.objects):
                if (o.name.startswith(("MoGe_Pano_", "MoGe_Splats", "MoGe_Camera", "MoGe_Geometry"))
                        or o.name == PANO_RIG):
                    try:
                        bpy.data.objects.remove(o, do_unlink=True)
                    except Exception:
                        pass
            for c in list(bpy.data.collections):
                if c.name.startswith("Pano F"):
                    try:
                        bpy.data.collections.remove(c)
                    except Exception:
                        pass
            purge_orphaned_moge_datablocks()

            rig, cams = _build_pano_rig(context, yaws, pitches)
            cam_by_face = {i: c for i, c in enumerate(cams)}

            def _move(ob, col):
                try:
                    for c in list(ob.users_collection):
                        try:
                            c.objects.unlink(ob)
                        except Exception:
                            pass
                    col.objects.link(ob)
                except Exception:
                    pass

            built = 0
            for fi in present:
                idx = plan[fi]
                co = cam_by_face.get(fi)
                if co is None:
                    continue
                # camera-local coords so cloud + camera travel (and hide) together
                Rnp = np.array(co.matrix_world.to_3x3(), dtype=np.float64)
                local = (xyz[idx].astype(np.float64) @ Rnp).astype(np.float32)
                oname = f"MoGe_Pano_F{fi:02d}"
                ob = _new_splat_object(
                    context, local, C[idx], D[idx].astype(np.float32), radii[idx], fx,
                    float(props.radius_scale), radius_fallback,
                    warn=lambda mm: self.report({'WARNING'}, mm),
                    extra_attrs={"PanoFace": np.full(len(idx), fi, dtype=np.float32)},
                    obj_name=oname)
                try:
                    ob["moge_kind"] = "pano"
                    ob["moge_face"] = int(fi)
                except Exception:
                    pass
                try:
                    ob.parent = co
                    ob.matrix_parent_inverse.identity()
                except Exception:
                    pass
                if len(yaws) == 4:
                    face_names = ["Front", "Right", "Back", "Left"]
                elif len(yaws) == 6:
                    face_names = ["Front", "Right", "Back", "Left", "Ceiling", "Floor"]
                else:
                    face_names = [f"Side {i}" for i in range(len(yaws) - 2)] + ["Ceiling", "Floor"] if len(yaws) >= 2 else [f"Face {i}" for i in range(len(yaws))]
                flabel = face_names[fi] if fi < len(face_names) else f"face {fi}"
                cname = f"Pano F{fi:02d} ({flabel})"
                fcol = bpy.data.collections.get(cname)
                if fcol is None:
                    fcol = bpy.data.collections.new(cname)
                    try:
                        context.scene.collection.children.link(fcol)
                    except Exception:
                        pass
                _move(co, fcol)
                _move(ob, fcol)
                built += len(idx)
            try:
                context.view_layer.update()
            except Exception:
                pass
            if cams:
                context.scene.camera = cams[0]

            context.scene.render.resolution_x = 2048
            context.scene.render.resolution_y = 2048
            context.scene.unit_settings.system = "METRIC"
            try:
                props.last_scan_folder = str(cache_dir)
                props.last_scanned_image = str(Path(target_path).resolve())
                props.metric_dim_text = f"{built:,} pano splats | {len(present)} faces | r: {radius_src}"
                props.depth_range_text = (f"Depth {float(np.min(D)):.2f}m..{float(np.max(D)):.2f}m | "
                                          f"seam {seam_s} | fit post {post:.4f}")
            except Exception:
                pass
            self.report({'INFO'}, f"Room ready: {built:,} splats in {len(present)} toggleable faces, seam {seam_s}")
            return {'FINISHED'}
        finally:
            try:
                prefs_edit.use_global_undo = prev_undo
            except Exception:
                pass

