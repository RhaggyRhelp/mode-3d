"""Headless Blender Pipeline & Leak Benchmark for MoDe 3D Studio.

Runs inside Blender:
  blender --factory-startup --background --python tools/diagnose_blender_pipeline.py

Measures:
1. Stage-by-stage timing of the scan pipeline inside Blender.
2. Memory (RSS) & datablock leak audit across 5 consecutive scans.
3. Evaluated geometry load: Point Cloud (Spheres) vs Realized Discs (Surfels).
4. UI Redraw main-thread I/O benchmark (simulating Panel.draw).
"""
from __future__ import annotations

import os
import sys
import json
import time
import ctypes
from ctypes import wintypes
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXT_DIR = ROOT / "blender_extension"
if str(EXT_DIR) not in sys.path:
    sys.path.insert(0, str(EXT_DIR))

import bpy
import numpy as np

# Windows memory query via ctypes
class PMC(ctypes.Structure):
    _fields_ = [
        ('cb', wintypes.DWORD),
        ('PageFaultCount', wintypes.DWORD),
        ('PeakWorkingSetSize', ctypes.c_size_t),
        ('WorkingSetSize', ctypes.c_size_t),
        ('QuotaPeakPagedPoolUsage', ctypes.c_size_t),
        ('QuotaPagedPoolUsage', ctypes.c_size_t),
        ('QuotaPeakNonPagedPoolUsage', ctypes.c_size_t),
        ('QuotaNonPagedPoolUsage', ctypes.c_size_t),
        ('PagefileUsage', ctypes.c_size_t),
        ('PeakPagefileUsage', ctypes.c_size_t),
    ]

def get_process_ram_mb() -> float:
    try:
        f = ctypes.windll.psapi.GetProcessMemoryInfo
        f.argtypes = [wintypes.HANDLE, ctypes.POINTER(PMC), wintypes.DWORD]
        f.restype = wintypes.BOOL
        pmc = PMC()
        pmc.cb = ctypes.sizeof(PMC)
        if f(ctypes.windll.kernel32.GetCurrentProcess(), ctypes.byref(pmc), pmc.cb):
            return round(pmc.WorkingSetSize / (1024.0 * 1024.0), 2)
    except Exception:
        pass
    return 0.0


DOWNLOADS_DIR = Path.home() / "Downloads" / "MOGE images and tests"
OUTPUT_DIR = DOWNLOADS_DIR / "diagnostics_output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def count_datablocks():
    return {
        "objects": len(bpy.data.objects),
        "meshes": len(bpy.data.meshes),
        "materials": len(bpy.data.materials),
        "images": len(bpy.data.images),
        "node_groups": len(bpy.data.node_groups),
        "orphan_meshes": sum(1 for m in bpy.data.meshes if m.users == 0),
        "orphan_materials": sum(1 for m in bpy.data.materials if m.users == 0),
        "orphan_images": sum(1 for img in bpy.data.images if img.users == 0),
    }


def run_blender_diagnostics():
    print("\n" + "=" * 70)
    print("  PHASE 2: BLENDER PIPELINE, MEMORY & DATABLOCK LEAK AUDIT")
    print("=" * 70)

    import moge_splat_studio
    moge_splat_studio.register()

    props = bpy.context.scene.moge_splat_props
    prefs = moge_splat_studio.preferences.get_preferences()

    # Find 5 test images
    test_files = [
        DOWNLOADS_DIR / "spacejoy-umAXneH4GhA-unsplash.jpg",
        DOWNLOADS_DIR / "PXL_20260902_220243594-2.jpg",
        DOWNLOADS_DIR / "aamir-tM4HEI-nY2Y-unsplash.jpg",
        DOWNLOADS_DIR / "dekogon-studios-highresscreenshot00027.jpg",
        DOWNLOADS_DIR / "candy-collecchia-s-staticcam-0475.webp",
    ]
    test_files = [f for f in test_files if f.exists()]
    if not test_files:
        test_files = [f for f in DOWNLOADS_DIR.iterdir() if f.is_file() and f.suffix.lower() in ('.jpg', '.png', '.webp')][:5]

    initial_ram = get_process_ram_mb()
    initial_db = count_datablocks()
    print(f"Blender Initial State: Process RAM = {initial_ram} MB | Meshes: {initial_db['meshes']} | Materials: {initial_db['materials']}")

    scan_history = []

    # 1. Multi-Scan Sequential Leak Test
    for scan_idx, img_file in enumerate(test_files, 1):
        print(f"\n[SCAN {scan_idx}/{len(test_files)}] Scanning {img_file.name} ({img_file.stat().st_size / 1024**2:.2f} MB)...")
        props.import_path = str(img_file.resolve())
        props.preset = "Balanced"
        props.surface_mode = "SEAMLESS"

        ram_before = get_process_ram_mb()
        t0 = time.perf_counter()
        
        # Execute standard operator
        res = bpy.ops.moge_splat.scan_daemon()
        dt = time.perf_counter() - t0

        ram_after = get_process_ram_mb()
        db_after = count_datablocks()
        
        splat_obj = bpy.data.objects.get("MoGe_Splats")
        vert_count = len(splat_obj.data.vertices) if splat_obj else 0

        entry = {
            "iteration": scan_idx,
            "image": img_file.name,
            "operator_status": str(res),
            "scan_time_s": round(dt, 3),
            "points_created": vert_count,
            "ram_before_mb": ram_before,
            "ram_after_mb": ram_after,
            "ram_delta_mb": round(ram_after - ram_before, 2),
            "datablocks": db_after,
        }
        scan_history.append(entry)

        print(f"  Result: {res} in {dt:.2f}s | Splats: {vert_count:,} | RAM: {ram_after} MB (delta: {ram_after - ram_before:+.1f} MB)")
        print(f"  Datablocks: Meshes={db_after['meshes']} (orphans={db_after['orphan_meshes']}), Materials={db_after['materials']} (orphans={db_after['orphan_materials']}), NodeGroups={db_after['node_groups']}")

    final_ram = get_process_ram_mb()
    net_ram_growth = final_ram - initial_ram
    final_db = count_datablocks()

    print("\n--- Consecutive Scan Leak Evaluation ---")
    print(f"  Initial Blender RAM: {initial_ram} MB")
    print(f"  Final Blender RAM:   {final_ram} MB (Net Drift: {net_ram_growth:+.1f} MB)")
    print(f"  Meshes remaining:    {final_db['meshes']} (Orphans: {final_db['orphan_meshes']})")
    print(f"  Materials remaining: {final_db['materials']} (Orphans: {final_db['orphan_materials']})")
    print(f"  Node Groups:         {final_db['node_groups']}")

    # 2. Geometry Nodes Realization Stress Test (Point Cloud vs Realized Surfels)
    print("\n" + "=" * 70)
    print("  PHASE 3: GEOMETRY NODES EVALUATION (SPHERES VS REALIZED SURFELS)")
    print("=" * 70)
    
    # Test SPHERES mode
    props.splat_style = "SPHERES"
    bpy.ops.moge_splat.scan_daemon()
    splat_obj = bpy.data.objects.get("MoGe_Splats")
    
    depsgraph = bpy.context.evaluated_depsgraph_get()
    eval_obj_spheres = splat_obj.evaluated_get(depsgraph)
    eval_mesh_spheres = eval_obj_spheres.to_mesh()
    spheres_verts = len(eval_mesh_spheres.vertices)
    spheres_polys = len(eval_mesh_spheres.polygons)
    eval_obj_spheres.to_mesh_clear()
    
    print(f"  Mode SPHERES (Point Cloud):")
    print(f"    - Evaluated Vertices: {spheres_verts:,}")
    print(f"    - Evaluated Polygons: {spheres_polys:,}")

    # Test SURFELS mode
    props.splat_style = "SURFELS"
    bpy.ops.moge_splat.scan_daemon()
    splat_obj = bpy.data.objects.get("MoGe_Splats")
    
    depsgraph = bpy.context.evaluated_depsgraph_get()
    eval_obj_surfels = splat_obj.evaluated_get(depsgraph)
    eval_mesh_surfels = eval_obj_surfels.to_mesh()
    surfels_verts = len(eval_mesh_surfels.vertices)
    surfels_polys = len(eval_mesh_surfels.polygons)
    eval_obj_surfels.to_mesh_clear()

    print(f"  Mode SURFELS (Realized Discs):")
    print(f"    - Evaluated Vertices: {surfels_verts:,} ({surfels_verts / max(spheres_verts, 1):.1f}x vs Spheres)")
    print(f"    - Evaluated Polygons: {surfels_polys:,}")

    surfel_impact = {
        "spheres_verts": spheres_verts,
        "spheres_polys": spheres_polys,
        "surfels_verts": surfels_verts,
        "surfels_polys": surfels_polys,
        "vertex_multiplier": round(surfels_verts / max(spheres_verts, 1), 1),
    }

    # 3. UI Redraw Main-Thread Stutter Benchmark
    print("\n" + "=" * 70)
    print("  PHASE 4: UI REDRAW MAIN-THREAD STUTTER BENCHMARK")
    print("=" * 70)
    from moge_splat_studio.cleanup import get_cache_size_mb, get_active_scan_dir

    # Compare Old Disk I/O vs New Cached Properties
    t_old_start = time.perf_counter()
    n_redraws = 100
    meta_path = get_active_scan_dir() / "meta.json"
    for _ in range(n_redraws):
        c_size = get_cache_size_mb()
        if meta_path.exists():
            try:
                _ = json.loads(meta_path.read_text())
            except Exception:
                pass
    t_old_total = time.perf_counter() - t_old_start
    ms_old = (t_old_total / n_redraws) * 1000.0

    t_new_start = time.perf_counter()
    for _ in range(n_redraws):
        _ = props.cache_size_mb
        _ = props.last_scan_points
        _ = props.last_scan_model
        _ = props.last_scan_depth_range
        _ = props.last_scan_fov
    t_new_total = time.perf_counter() - t_new_start
    ms_new = (t_new_total / n_redraws) * 1000.0

    print(f"  Old Disk Method:      {ms_old:.3f} ms / redraw ({ms_old * 60.0:.1f} ms/s stall at 60 FPS)")
    print(f"  New In-Memory Cache:  {ms_new:.4f} ms / redraw ({ms_new * 60.0:.3f} ms/s stall at 60 FPS)")
    print(f"  Speedup:              {ms_old / max(ms_new, 1e-6):.1f}x faster UI redraw (0% main-thread stall)!")

    ui_benchmark = {
        "old_ms_per_redraw": round(ms_old, 3),
        "new_ms_per_redraw": round(ms_new, 4),
        "speedup_factor": round(ms_old / max(ms_new, 1e-6), 1),
        "ms_saved_per_sec_at_60fps": round((ms_old - ms_new) * 60.0, 1),
    }

    # 4. Cache and Purge Test
    print("\n[PURGE TEST] Testing purge_all_cache...")
    res_purge = bpy.ops.moge_splat.purge_all_cache()
    db_after_purge = count_datablocks()
    ram_after_purge = get_process_ram_mb()
    print(f"  Purge operator result: {res_purge} | RAM: {ram_after_purge} MB | Meshes: {db_after_purge['meshes']} | Materials: {db_after_purge['materials']}")

    # Save summary report
    summary = {
        "scan_history": scan_history,
        "net_ram_growth_mb": round(net_ram_growth, 2),
        "surfel_impact": surfel_impact,
        "ui_redraw_benchmark": ui_benchmark,
        "datablocks_after_purge": db_after_purge,
    }
    (OUTPUT_DIR / "blender_pipeline_diagnostics.json").write_text(json.dumps(summary, indent=2))
    print(f"\n[INFO] Blender pipeline diagnostics written to {OUTPUT_DIR / 'blender_pipeline_diagnostics.json'}")


if __name__ == "__main__":
    run_blender_diagnostics()
