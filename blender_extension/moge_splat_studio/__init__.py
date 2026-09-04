bl_info = {
    "name": "MoGe Splat Studio",
    "author": "Navneeth & MoGe Splat Studio Contributors",
    "version": (2, 1, 0),
    "blender": (4, 2, 0),
    "location": "View3D > Sidebar > MoGe Splat",
    "description": "Warm-daemon metric point-splats, metric camera, and 2.5D compositor relighter based on Microsoft MoGe-3",
    "category": "Import-Export",
    "doc_url": "https://github.com/microsoft/MoGe",
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
