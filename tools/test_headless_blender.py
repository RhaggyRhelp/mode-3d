"""Headless verification of MoDe 3D Studio Blender extension.

Runs inside Blender background mode to verify:
1. Clean RNA registration
2. Property groups & preset automation
3. All 12 operators registered in bpy.ops.moge_splat
4. Live end-to-end scan pipeline execution (if daemon is running)
5. Geometry Nodes & Material tree generation
6. Viewport radius adjustment & camera matching
7. 2.5D compositor relighter graph construction
8. Floor levelling execution
9. Cache and datablock purging
"""
import sys
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXT_DIR = ROOT / "blender_extension"
if str(EXT_DIR) not in sys.path:
    sys.path.insert(0, str(EXT_DIR))

import bpy
import moge_splat_studio


def run_tests():
    print("\n=======================================================")
    print("  MoDe 3D Studio - Headless Blender Verification Suite ")
    print("=======================================================")

    # 1. Register extension
    if not hasattr(bpy.context.scene, "moge_splat_props"):
        print("[TEST 1/8] Registering moge_splat_studio...")
        moge_splat_studio.register()
    else:
        print("[TEST 1/8] moge_splat_studio already loaded by Blender extension system.")

    # 2. Verify scene properties and presets
    print("[TEST 2/8] Verifying scene properties & preset automation...")
    assert hasattr(bpy.context.scene, "moge_splat_props"), "moge_splat_props missing from Scene!"
    props = bpy.context.scene.moge_splat_props

    # Test preset switching
    props.preset = "Balanced"
    assert props.model_version == "v3", f"Expected v3, got {props.model_version}"
    assert props.max_size == 1536, f"Expected 1536, got {props.max_size}"

    props.preset = "Quality"
    assert props.max_size == 2448, f"Expected 2448, got {props.max_size}"
    assert props.refine_steps == 3, f"Expected 3, got {props.refine_steps}"

    props.preset = "Draft"
    assert props.model_version == "v3", f"Expected v3, got {props.model_version}"
    assert props.refine_steps == 0, f"Expected 0, got {props.refine_steps}"
    assert props.max_size == 1024, f"Expected 1024, got {props.max_size}"
    print("  [OK] Scene properties and preset automation verified.")

    # 3. Verify all 12 operators registered in bpy.ops.moge_splat
    print("[TEST 3/8] Verifying registered operators...")
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
        "set_resolution",
    ]
    for op_name in expected_ops:
        assert hasattr(bpy.ops.moge_splat, op_name), f"Operator bpy.ops.moge_splat.{op_name} missing!"
    print(f"  [OK] All {len(expected_ops)} operators verified in bpy.ops.moge_splat.")

    # 4. Test set_resolution operator
    print("[TEST 4/8] Testing set_resolution operator...")
    res_op = bpy.ops.moge_splat.set_resolution(resolution=4096)
    assert res_op == {'FINISHED'}, f"set_resolution failed: {res_op}"
    assert props.max_size == 4096, f"Expected max_size 4096, got {props.max_size}"
    props.preset = "Balanced"
    print("  [OK] set_resolution operator executed successfully.")

    # 5. Check daemon health via operator
    print("[TEST 5/8] Checking daemon connectivity...")
    daemon_op_res = bpy.ops.moge_splat.ensure_daemon()
    assert daemon_op_res == {'FINISHED'}, f"ensure_daemon operator failed: {daemon_op_res}"

    from moge_splat_studio.network import daemon_health
    state, payload = daemon_health()
    daemon_online = (state == "ok")
    if daemon_online:
        print(f"  [OK] Daemon is online on port 8766 (models: {payload.get('models_loaded', [])})")
    else:
        print(f"  [SKIP] Daemon is not online ({state}: {payload}). Skipping live scan tests.")

    # 6. Live end-to-end scan pipeline test (if daemon is up)
    if daemon_online:
        print("[TEST 6/8] Executing live scan_daemon operator with test pattern...")
        test_img = ROOT / "tests" / "test_data" / "test_pattern.jpg"
        assert test_img.exists(), f"Missing test pattern image: {test_img}"

        props.import_path = str(test_img.resolve())
        props.preset = "Draft"
        props.surface_mode = "SEAMLESS"

        scan_res = bpy.ops.moge_splat.scan_daemon()
        assert scan_res == {'FINISHED'}, f"scan_daemon operator failed: {scan_res}"

        # Verify MoGe_Splats object
        splat_obj = bpy.data.objects.get("MoGe_Splats")
        assert splat_obj is not None, "MoGe_Splats object was not created in scene!"
        n_verts = len(splat_obj.data.vertices)
        assert n_verts > 0, f"Expected vertices > 0, got {n_verts}"
        print(f"  [OK] MoGe_Splats created with {n_verts:,} vertices.")

        # Verify mesh attributes
        attrs = [a.name for a in splat_obj.data.attributes]
        color_attrs = [a.name for a in splat_obj.data.color_attributes]
        assert "Color" in color_attrs, f"'Color' missing from color attributes: {color_attrs}"
        assert "SplatDepth" in attrs, f"'SplatDepth' missing from attributes: {attrs}"
        assert "SplatRadius" in attrs, f"'SplatRadius' missing from attributes: {attrs}"
        assert "SplatNormal" in attrs, f"'SplatNormal' missing from attributes: {attrs}"
        print(f"  [OK] Mesh attributes verified: {attrs}, Color: {color_attrs}")

        # Verify Geometry Nodes modifier
        mod = splat_obj.modifiers.get("MoGe_Splat_Viewer")
        assert mod is not None and mod.type == 'NODES', "Geometry Nodes modifier missing!"
        assert mod.node_group is not None, "Modifier node_group is None!"
        print(f"  [OK] Geometry Nodes graph active: {mod.node_group.name}")

        # Verify Material
        mat = bpy.data.materials.get("M_MoGe_Splat")
        assert mat is not None and getattr(mat, "node_tree", None) is not None, "Material M_MoGe_Splat missing or has no node_tree!"
        print(f"  [OK] Material verified: {mat.name}")

        # Verify Camera
        cam_obj = bpy.data.objects.get("MoGe_Camera")
        assert cam_obj is not None, "MoGe_Camera missing!"
        assert cam_obj.data.lens > 0.0, f"Invalid camera lens: {cam_obj.data.lens}"
        assert cam_obj.data.show_passepartout is True, "show_passepartout not True!"
        assert cam_obj.data.passepartout_alpha == 1.0, f"passepartout_alpha expected 1.0, got {cam_obj.data.passepartout_alpha}"
        assert bpy.context.scene.render.resolution_x > 0, "resolution_x not set!"
        assert bpy.context.scene.render.resolution_y > 0, "resolution_y not set!"
        print(f"  [OK] MoGe_Camera created (lens: {cam_obj.data.lens:.1f}mm, passepartout: {cam_obj.data.passepartout_alpha}, res: {bpy.context.scene.render.resolution_x}x{bpy.context.scene.render.resolution_y}).")

        # 7. Test secondary operators on the live scan
        print("[TEST 7/8] Testing secondary operators (radius, camera, relight, level)...")
        # Update radius
        props.radius_scale = 1.25
        res_rad = bpy.ops.moge_splat.update_radius()
        assert res_rad == {'FINISHED'}, f"update_radius failed: {res_rad}"

        # View camera
        res_cam = bpy.ops.moge_splat.view_camera()
        assert res_cam == {'FINISHED'}, f"view_camera failed: {res_cam}"

        # Setup relight
        res_rel = bpy.ops.moge_splat.setup_relight()
        assert res_rel == {'FINISHED'}, f"setup_relight failed: {res_rel}"

        # Level auto
        res_lvl = bpy.ops.moge_splat.level_auto()
        assert res_lvl == {'FINISHED'}, f"level_auto failed: {res_lvl}"
        print("  [OK] Secondary operators executed cleanly without errors.")
    else:
        print("[TEST 6/8] Skipped live scan (daemon offline).")
        print("[TEST 7/8] Skipped secondary operators (daemon offline).")

    # 8. Test cache purge operator execution
    print("[TEST 8/8] Testing cache purge and datablock cleanup...")
    res = bpy.ops.moge_splat.purge_all_cache()
    assert res == {'FINISHED'}, f"purge_all_cache failed with status: {res}"
    print("  [OK] Cache and datablock purge operator executed successfully.")

    print("\n=======================================================")
    print("   >>> ALL HEADLESS BLENDER HEALTH CHECKS PASSED! <<<   ")
    print("=======================================================\n")


if __name__ == "__main__":
    run_tests()
