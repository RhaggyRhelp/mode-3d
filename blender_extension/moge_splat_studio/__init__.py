bl_info = {
    "name": "MoDe 3D Studio",
    "author": "MeshHead & Contributors",
    "version": (2, 1, 0),
    "blender": (4, 2, 0),
    "location": "View3D > Sidebar > MoDe 3D",
    "description": "MoDe 3D: Metric Monocular Depth & Relighting Studio for Blender (4.2+ / 5.x)",
    "category": "Import-Export",
    "doc_url": "https://github.com/RhaggyRhelp/mode-3d",
}

import bpy
from bpy.props import PointerProperty

from .preferences import MoGeAddonPreferences
from .properties import MoGeSplatProperties
from .cleanup import MOGE_OT_purge_all_cache
from .operators import (
    MOGE_OT_ensure_daemon,
    MOGE_OT_stop_daemon,
    MOGE_OT_scan_splat_daemon,
    MOGE_OT_update_splat_radius,
    MOGE_OT_view_camera,
    MOGE_OT_setup_compositor_relight,
    MOGE_OT_level_auto,
    MOGE_OT_level_markers_add,
    MOGE_OT_level_markers_apply,
    MOGE_OT_level_remove,
    MOGE_OT_set_resolution,
)
from .ui import VIEW3D_PT_moge_splat

CLASSES = (
    MoGeAddonPreferences,
    MoGeSplatProperties,
    MOGE_OT_ensure_daemon,
    MOGE_OT_stop_daemon,
    MOGE_OT_scan_splat_daemon,
    MOGE_OT_update_splat_radius,
    MOGE_OT_view_camera,
    MOGE_OT_setup_compositor_relight,
    MOGE_OT_level_auto,
    MOGE_OT_level_markers_add,
    MOGE_OT_level_markers_apply,
    MOGE_OT_level_remove,
    MOGE_OT_set_resolution,
    MOGE_OT_purge_all_cache,
    VIEW3D_PT_moge_splat,
)


def register():
    for cls in CLASSES:
        bpy.utils.register_class(cls)
    bpy.types.Scene.moge_splat_props = PointerProperty(type=MoGeSplatProperties)


def unregister():
    if hasattr(bpy.types.Scene, "moge_splat_props"):
        try:
            del bpy.types.Scene.moge_splat_props
        except Exception:
            pass
    for cls in reversed(CLASSES):
        try:
            bpy.utils.unregister_class(cls)
        except Exception:
            pass


if __name__ == "__main__":
    register()
