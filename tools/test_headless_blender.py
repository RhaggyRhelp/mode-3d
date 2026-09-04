"""Headless verification of MoGe Splat Studio Blender extension.

Runs inside Blender background mode to verify clean RNA registration,
operator availability, and cache purge execution.
"""
import sys
from pathlib import Path

# Add extension source to Python path
ROOT = Path(__file__).resolve().parents[1]
EXT_DIR = ROOT / "blender_extension"
if str(EXT_DIR) not in sys.path:
    sys.path.insert(0, str(EXT_DIR))

import bpy
import moge_splat_studio


def run_tests():
    # Register if not already loaded by Blender extensions system
    if not hasattr(bpy.context.scene, "moge_splat_props"):
        print("[TEST] Registering moge_splat_studio...")
        moge_splat_studio.register()
    else:
        print("[TEST] moge_splat_studio already loaded by Blender extension system.")

    # 1. Verify scene properties
    assert hasattr(bpy.context.scene, "moge_splat_props"), "moge_splat_props missing from Scene!"
    props = bpy.context.scene.moge_splat_props
    assert props.preset == "Balanced", f"Expected default preset 'Balanced', got {props.preset}"
    assert props.model_version == "v3", f"Expected default model 'v3', got {props.model_version}"
    print("  [OK] Scene properties verified.")

    # 2. Verify all 11 operators registered in bpy.ops.moge_splat
    expected_ops = [
        "scan_daemon",
        "ensure_daemon",
        "stop_daemon",
        "update_radius",
        "view_camera",
        "setup_relight",
        "level_auto",
        "level_markers_add",
        "level_markers_apply",
        "level_remove",
        "purge_all_cache",
    ]
    for op_name in expected_ops:
        assert hasattr(bpy.ops.moge_splat, op_name), f"Operator bpy.ops.moge_splat.{op_name} missing!"
    print(f"  [OK] All {len(expected_ops)} operators verified in bpy.ops.moge_splat.")

    # 3. Test cache purge operator execution
    res = bpy.ops.moge_splat.purge_all_cache()
    assert res == {'FINISHED'}, f"purge_all_cache failed with status: {res}"
    print("  [OK] Cache and datablock purge operator executed successfully.")

    print("\n>>> ALL HEADLESS BLENDER TESTS PASSED! <<<\n")


if __name__ == "__main__":
    run_tests()
