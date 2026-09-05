import bpy
from bpy.props import PointerProperty
from bpy.app.handlers import persistent

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


@persistent
def _on_blender_exit(dummy=None):
    from .network import daemon_stop
    try:
        daemon_stop()
    except Exception:
        pass


def register():
    for cls in CLASSES:
        bpy.utils.register_class(cls)
    bpy.types.Scene.moge_splat_props = PointerProperty(type=MoGeSplatProperties)

    if hasattr(bpy.app.handlers, "exit_pre"):
        if _on_blender_exit not in bpy.app.handlers.exit_pre:
            bpy.app.handlers.exit_pre.append(_on_blender_exit)


def unregister():
    if hasattr(bpy.app.handlers, "exit_pre"):
        if _on_blender_exit in bpy.app.handlers.exit_pre:
            bpy.app.handlers.exit_pre.remove(_on_blender_exit)

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
