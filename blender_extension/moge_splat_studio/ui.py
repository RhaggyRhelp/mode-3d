"""User Interface Panels for MoGe Splat Studio."""
from __future__ import annotations

import json
from pathlib import Path

import bpy
from bpy.types import Panel

from .cleanup import get_cache_size_mb, get_active_scan_dir


class VIEW3D_PT_moge_splat(Panel):
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'MoGe Splat'
    bl_label = 'MoGe Splat Studio'

    def draw(self, context):
        layout = self.layout
        props = context.scene.moge_splat_props

        # Segmented Mode Switcher (Simple vs Advanced)
        layout.prop(props, "ui_mode", expand=True)

        # 1. Source Image
        col = layout.column(align=True)
        col.label(text="1. Source Image:", icon='FILE_IMAGE')
        col.prop(props, "import_path", text="")

        if props.ui_mode == 'SIMPLE':
            # -------------------------------------------------------------
            # SIMPLE MODE: Fast, intuitive 1-click workflow
            # -------------------------------------------------------------
            box = layout.box()
            box.label(text="2. Quality & Resolution:", icon='PREFERENCES')
            box.prop(props, "preset", text="Preset")

            # 1-Click Resolution Quick Tiers
            row_res = box.row(align=True)
            row_res.label(text="Resolution:")
            sub_res = row_res.row(align=True)
            sub_res.operator("moge_splat.set_resolution", text="1536", depress=(props.max_size == 1536)).resolution = 1536
            sub_res.operator("moge_splat.set_resolution", text="2448", depress=(props.max_size == 2448)).resolution = 2448
            sub_res.operator("moge_splat.set_resolution", text="4096", depress=(props.max_size == 4096)).resolution = 4096

            # Geometry Iterations (max 7)
            box.prop(props, "refine_steps", text="Iterations (0-7)")

            # Scene Setup & Shading
            sbox = layout.box()
            sbox.label(text="3. Scene Setup:", icon='MESH_ICOSPHERE')
            sbox.prop(props, "surface_mode", text="Boundary")
            if props.surface_mode == 'ISLANDS':
                sbox.prop(props, "apply_mask", text="Cut Voids")
            sbox.prop(props, "shading_mode", text="Lighting")

        else:
            # -------------------------------------------------------------
            # ADVANCED MODE: Complete artistic control with simplified terms
            # -------------------------------------------------------------
            # 1. Presets & Resolution
            rbox = layout.box()
            rbox.label(text="2. Resolution & Presets:", icon='PREFERENCES')
            rbox.prop(props, "preset", text="Preset")

            row_res = rbox.row(align=True)
            row_res.label(text="Resolution:")
            sub_res = row_res.row(align=True)
            sub_res.operator("moge_splat.set_resolution", text="1536", depress=(props.max_size == 1536)).resolution = 1536
            sub_res.operator("moge_splat.set_resolution", text="2448", depress=(props.max_size == 2448)).resolution = 2448
            sub_res.operator("moge_splat.set_resolution", text="4096", depress=(props.max_size == 4096)).resolution = 4096
            rbox.prop(props, "max_size", text="Custom (px)")

            # 2. AI Geometry Quality
            qbox = layout.box()
            qbox.label(text="3. AI Geometry Quality:", icon='SETTINGS')
            row_ai = qbox.row(align=True)
            row_ai.prop(props, "model_variant", text="Model")
            row_ai.prop(props, "resolution_level", text="Detail")
            qbox.prop(props, "refine_steps", text="Iterations (0-7)")
            qbox.prop(props, "tta_mode", text="Anti-Jitter")

            # Camera lens override
            row_fov = qbox.row(align=True)
            row_fov.prop(props, "use_custom_fov", text="Manual Lens")
            if props.use_custom_fov:
                row_fov.prop(props, "custom_fov", text="FOV°")

            # 3. Scene Boundary & Masking
            sbox = layout.box()
            sbox.label(text="4. Environment Boundary:", icon='MESH_ICOSPHERE')
            sbox.prop(props, "surface_mode", text="Boundary")
            if props.surface_mode == 'ISLANDS':
                sbox.prop(props, "apply_mask", text="Cut Voids")

            # 4. Viewport & Point Display
            dbox = layout.box()
            dbox.label(text="5. Points & Viewport:", icon='POINTCLOUD_DATA')
            row_disp = dbox.row(align=True)
            row_disp.prop(props, "splat_style", text="Style")
            row_disp.prop(props, "shading_mode", text="Lighting")
            dbox.prop(props, "point_budget", text="Point Limit")
            dbox.prop(props, "fullres_color", text="High-Res Colors")

            row_scale = dbox.row(align=True)
            row_scale.prop(props, "radius_scale", text="Gap Fill")
            row_scale.prop(props, "splat_radius", text="Fixed (m)")
            dbox.operator("moge_splat.update_radius", text="Apply Point Sizing to Viewport", icon='FILE_REFRESH')

            # 5. Grid Levelling
            lbox = layout.box()
            lbox.label(text="6. Align Floor to Grid (Z=0):", icon='ORIENTATION_GLOBAL')
            lbox.operator("moge_splat.level_auto", text="Align Floor (Auto)", icon='SNAP_FACE')
            row_m = lbox.row(align=True)
            row_m.operator("moge_splat.level_markers_add", text="Add Markers", icon='ADD')
            row_m.operator("moge_splat.level_markers_apply", text="Align to Markers", icon='CHECKMARK')
            lbox.operator("moge_splat.level_remove", text="Reset Alignment", icon='X')

        # Primary Action Button
        layout.separator()
        btn_col = layout.column()
        btn_col.scale_y = 1.6
        btn_col.operator("moge_splat.scan_daemon", text="Generate 3D Splats", icon='RESTRICT_RENDER_OFF')

        # Post-Scan Quick Actions
        row_post = layout.row(align=True)
        row_post.operator("moge_splat.view_camera", text="Snap to Camera", icon='CAMERA_DATA')
        row_post.operator("moge_splat.level_auto", text="Align Floor", icon='SNAP_FACE')
        row_post.operator("moge_splat.setup_relight", text="Relight Scene", icon='LIGHT_SUN')

        # Diagnostics & Last Scan Info
        meta_file = get_active_scan_dir() / "meta.json"
        if meta_file.exists():
            try:
                meta = json.loads(meta_file.read_text())
                diag_box = layout.box()
                diag_box.label(text="Last Scan Diagnostics:", icon='INFO')
                diag_box.label(text=f"Points: {meta.get('points', 0):,} | Engine: {meta.get('model_version', '')}/{meta.get('variant', '')}")
                diag_box.label(text=f"Depth: {meta.get('min_depth', 0):.2f}m .. {meta.get('max_depth', 0):.2f}m")
                diag_box.label(text=f"FOV: {meta.get('fov_x', 0):.1f}° × {meta.get('fov_y', 0):.1f}° ({meta.get('fov_src', '')})")
            except Exception:
                pass

        # Cache & Clean Box
        cbox = layout.box()
        crow = cbox.row(align=True)
        cache_mb = get_cache_size_mb()
        crow.label(text=f"Cache: {cache_mb:.1f} MB", icon='DISK_DRIVE')
        crow.operator("moge_splat.purge_all_cache", text="Purge Cache", icon='TRASH')

        # Professional Accreditation Box
        abox = layout.box()
        abox.label(text="MoGe Splat Studio", icon='WORLD')
        abox.label(text="Core Architecture: Microsoft MoGe-3")
        abox.label(text="Wang, Qian, et al. (CVPR / NeurIPS)")
