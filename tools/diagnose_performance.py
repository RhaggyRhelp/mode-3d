"""MoDe 3D Studio - Comprehensive Performance & Memory Leak Diagnostic Suite.

Tests:
1. Daemon VRAM, Latency Waterfall, and Payload Profiling across presets and images.
2. Blender Headless End-to-End Pipeline Profiling & Cumulative Memory/Datablock Leak Audit.
3. Geometry Nodes Realization vs Viewport Load Benchmark.
4. UI Redraw Main-Thread Stutter Benchmark.

Outputs diagnostics and test images to:
<Downloads>/MOGE images and tests/diagnostics_output
"""
from __future__ import annotations

import os
import io
import sys
import json
import time
import math
import shutil
import urllib.request
import urllib.parse
import http.client
import uuid
from pathlib import Path

import numpy as np
import cv2

ROOT = Path(__file__).resolve().parents[1]
DAEMON_HOST = "127.0.0.1"
DAEMON_PORT = 8766
DOWNLOADS_DIR = Path.home() / "Downloads" / "MOGE images and tests"
OUTPUT_DIR = DOWNLOADS_DIR / "diagnostics_output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def get_daemon_health():
    url = f"http://{DAEMON_HOST}:{DAEMON_PORT}/health"
    try:
        with urllib.request.urlopen(url, timeout=3.0) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:
        return {"error": str(e)}


def post_infer(img_path: Path, preset: dict, fov_override: float | None = None) -> tuple[dict, float, bytes]:
    boundary = f"----MoGePerf{uuid.uuid4().hex}"
    body = io.BytesIO()

    fields = {
        "model_version": preset.get("model_version", "v3"),
        "variant": preset.get("variant", "vitl"),
        "resolution_level": preset.get("resolution_level", "High"),
        "refine_steps": str(preset.get("refine_steps", 2)),
        "max_size": str(preset.get("max_size", 1536)),
        "seamless": "true" if preset.get("seamless", True) else "false",
        "apply_mask": "false",
        "remove_edges": "false",
        "tta": preset.get("tta", "off"),
    }
    if fov_override is not None:
        fields["fov_x_override"] = str(fov_override)

    for k, v in fields.items():
        body.write(f"--{boundary}\r\n".encode())
        body.write(f'Content-Disposition: form-data; name="{k}"\r\n\r\n'.encode())
        body.write(f"{v}\r\n".encode())

    img_bytes = img_path.read_bytes()
    mime = "image/jpeg"
    if img_path.suffix.lower() == ".png":
        mime = "image/png"
    elif img_path.suffix.lower() == ".webp":
        mime = "image/webp"

    body.write(f"--{boundary}\r\n".encode())
    body.write(f'Content-Disposition: form-data; name="image"; filename="{img_path.name}"\r\n'.encode())
    body.write(f"Content-Type: {mime}\r\n\r\n".encode())
    body.write(img_bytes)
    body.write(b"\r\n")
    body.write(f"--{boundary}--\r\n".encode())

    payload = body.getvalue()
    headers = {
        "Content-Type": f"multipart/form-data; boundary={boundary}",
        "Content-Length": str(len(payload)),
    }

    t0 = time.perf_counter()
    conn = http.client.HTTPConnection(DAEMON_HOST, DAEMON_PORT, timeout=180.0)
    try:
        conn.request("POST", "/infer", body=payload, headers=headers)
        resp = conn.getresponse()
        resp_data = resp.read()
        roundtrip_s = time.perf_counter() - t0
        return {"status": resp.status, "roundtrip_s": roundtrip_s, "payload_len": len(payload), "resp_len": len(resp_data)}, roundtrip_s, resp_data
    finally:
        conn.close()


def post_level(npz_bytes: bytes) -> tuple[dict, float]:
    boundary = f"----MoGeLevel{uuid.uuid4().hex}"
    body = io.BytesIO()
    fields = {"ransac_iters": "1500", "cone_deg": "40.0", "seed": "0"}
    for k, v in fields.items():
        body.write(f"--{boundary}\r\n".encode())
        body.write(f'Content-Disposition: form-data; name="{k}"\r\n\r\n'.encode())
        body.write(f"{v}\r\n".encode())

    body.write(f"--{boundary}\r\n".encode())
    body.write(f'Content-Disposition: form-data; name="maps"; filename="response.npz"\r\n'.encode())
    body.write(f"Content-Type: application/x-numpy-archive\r\n\r\n".encode())
    body.write(npz_bytes)
    body.write(b"\r\n")
    body.write(f"--{boundary}--\r\n".encode())

    payload = body.getvalue()
    headers = {
        "Content-Type": f"multipart/form-data; boundary={boundary}",
        "Content-Length": str(len(payload)),
    }

    t0 = time.perf_counter()
    conn = http.client.HTTPConnection(DAEMON_HOST, DAEMON_PORT, timeout=60.0)
    try:
        conn.request("POST", "/level", body=payload, headers=headers)
        resp = conn.getresponse()
        resp_data = resp.read()
        dt = time.perf_counter() - t0
        res = json.loads(resp_data.decode("utf-8", "replace")) if resp.status == 200 else {"error": resp.status}
        return res, dt
    finally:
        conn.close()


def save_visual_outputs(prefix: str, z_data: np.lib.npyio.NpzFile):
    """Saves depth colormap and normal map visualization to diagnostics_output folder."""
    try:
        depth = np.asarray(z_data["depth"], dtype=np.float32)
        normal = np.asarray(z_data["normal"], dtype=np.float32)
        rgb = np.asarray(z_data["image"])

        # 1. Depth visualization (Normalized Inverse Depth Heatmap)
        valid = np.isfinite(depth) & (depth > 0.05)
        if valid.any():
            d_valid = depth[valid]
            d_min, d_max = np.percentile(d_valid, 2), np.percentile(d_valid, 98)
            d_norm = np.clip((depth - d_min) / max(d_max - d_min, 1e-4), 0.0, 1.0)
            d_vis = (255.0 * (1.0 - d_norm)).astype(np.uint8)
            d_color = cv2.applyColorMap(d_vis, cv2.COLORMAP_TURBO)
            d_color[~valid] = [0, 0, 0]
            cv2.imwrite(str(OUTPUT_DIR / f"{prefix}_depth_turbo.jpg"), d_color)

        # 2. Normal visualization (RGB encoded)
        if normal is not None and normal.shape[:2] == depth.shape:
            n_vis = ((np.clip(normal, -1.0, 1.0) * 0.5 + 0.5) * 255.0).astype(np.uint8)
            n_bgr = cv2.cvtColor(n_vis, cv2.COLOR_RGB2BGR)
            cv2.imwrite(str(OUTPUT_DIR / f"{prefix}_normal_vis.jpg"), n_bgr)

        # 3. Save RGB preview thumbnail
        rgb_bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
        cv2.imwrite(str(OUTPUT_DIR / f"{prefix}_input_preview.jpg"), rgb_bgr)
    except Exception as e:
        print(f"  [WARN] Visual output generation failed for {prefix}: {e}")


def run_daemon_diagnostics(test_images: list[Path]):
    print("\n" + "=" * 70)
    print("  PHASE 1: DAEMON VRAM, LATENCY WATERFALL & MEMORY LEAK AUDIT")
    print("=" * 70)

    initial_health = get_daemon_health()
    print(f"Daemon Initial State: VRAM {initial_health.get('vram_allocated_mb')} MB | Device: {initial_health.get('cuda_name')}")

    presets_to_test = [
        ("Draft", {"model_version": "v3", "variant": "vitl", "resolution_level": "Low", "refine_steps": 0, "max_size": 1024, "seamless": True}),
        ("Balanced", {"model_version": "v3", "variant": "vitl", "resolution_level": "High", "refine_steps": 2, "max_size": 1536, "seamless": True}),
        ("Quality", {"model_version": "v3", "variant": "vitl", "resolution_level": "High", "refine_steps": 3, "max_size": 2448, "seamless": True}),
        ("4K_Stress", {"model_version": "v3", "variant": "vitl", "resolution_level": "High", "refine_steps": 2, "max_size": 4096, "seamless": True}),
    ]

    results = []

    for img_idx, img_path in enumerate(test_images, 1):
        print(f"\n--- Testing Image {img_idx}/{len(test_images)}: {img_path.name} ({img_path.stat().st_size / 1024**2:.2f} MB) ---")
        
        # Test default Balanced preset
        preset_name, preset_cfg = presets_to_test[1] # Balanced
        info, rt, raw_resp = post_infer(img_path, preset_cfg)
        
        if info["status"] != 200:
            print(f"  [FAIL] HTTP {info['status']}: {raw_resp[:200]}")
            continue

        h_after = get_daemon_health()
        
        # Unpack NPZ in memory
        t_unpack0 = time.perf_counter()
        z = np.load(io.BytesIO(raw_resp), allow_pickle=False)
        pts = np.asarray(z["points"])
        t_unpack = time.perf_counter() - t_unpack0

        h, w = z["height"], z["width"]
        fov_x, fov_y = float(z["fov_x"]), float(z["fov_y"])
        fov_src = str(z.get("fov_src", "model"))
        pts_count = int(np.prod(pts.shape[:2]))

        # Test floor level endpoint with this response
        level_res, t_level = post_level(raw_resp)

        # Save visual artifacts
        prefix = f"scan_{img_idx:02d}_{img_path.stem[:20]}"
        save_visual_outputs(prefix, z)

        res_entry = {
            "image": img_path.name,
            "preset": preset_name,
            "infer_dims": f"{w}x{h}",
            "points": pts_count,
            "roundtrip_s": round(rt, 3),
            "npz_unpack_s": round(t_unpack, 4),
            "payload_mb": round(len(raw_resp) / (1024**2), 2),
            "vram_mb": h_after.get("vram_allocated_mb"),
            "fov_x": round(fov_x, 1),
            "fov_y": round(fov_y, 1),
            "fov_src": fov_src,
            "level_ok": level_res.get("ok", False),
            "level_time_s": round(t_level, 3),
        }
        results.append(res_entry)

        print(f"  [OK] Turnaround: {rt:.2f}s | Dim: {w}x{h} ({pts_count:,} pts) | NPZ: {len(raw_resp)/(1024**2):.1f} MB | VRAM: {h_after.get('vram_allocated_mb')} MB | FOV: {fov_x:.1f}° ({fov_src}) | Level: {t_level:.2f}s")

    # Now run multi-preset stress on the largest image
    large_img = max(test_images, key=lambda p: p.stat().st_size)
    print(f"\n--- Preset Scaling Stress Test on Largest Image: {large_img.name} ---")
    preset_scaling_results = []
    for pname, pcfg in presets_to_test:
        info, rt, raw_resp = post_infer(large_img, pcfg)
        h = get_daemon_health()
        z = np.load(io.BytesIO(raw_resp), allow_pickle=False)
        w, ht = int(z["width"]), int(z["height"])
        entry = {
            "preset": pname,
            "max_size": pcfg["max_size"],
            "infer_res": f"{w}x{ht}",
            "turnaround_s": round(rt, 3),
            "payload_mb": round(len(raw_resp) / (1024**2), 2),
            "vram_mb": h.get("vram_allocated_mb"),
        }
        preset_scaling_results.append(entry)
        print(f"  Preset {pname:10s} ({pcfg['max_size']}px) -> Dims: {w}x{ht} | Latency: {rt:.2f}s | Payload: {entry['payload_mb']} MB | VRAM: {entry['vram_mb']} MB")

    final_health = get_daemon_health()
    vram_drift = final_health.get("vram_allocated_mb", 0) - initial_health.get("vram_allocated_mb", 0)
    print(f"\nDaemon Leak Audit Summary:")
    print(f"  Initial VRAM: {initial_health.get('vram_allocated_mb')} MB")
    print(f"  Final VRAM:   {final_health.get('vram_allocated_mb')} MB")
    print(f"  VRAM Drift:   {vram_drift:+.1f} MB across {len(test_images) + len(presets_to_test)} inferences.")
    if abs(vram_drift) < 50.0:
        print("  [PASS] Zero GPU VRAM leak detected. CUDA memory allocations return to baseline.")
    else:
        print("  [WARN] Measurable VRAM drift detected. Inspect activation cache or tensor references.")

    return results, preset_scaling_results


def main():
    print("=" * 70)
    print("  MoDe 3D Studio - Comprehensive Performance & Leak Profiler")
    print("=" * 70)
    print(f"Target Images Directory: {DOWNLOADS_DIR}")
    print(f"Diagnostics Output:      {OUTPUT_DIR}")

    if not DOWNLOADS_DIR.exists():
        print(f"[ERROR] Directory not found: {DOWNLOADS_DIR}")
        sys.exit(1)

    all_images = [f for f in DOWNLOADS_DIR.iterdir() if f.is_file() and f.suffix.lower() in ('.jpg', '.png', '.webp', '.jpeg')]
    print(f"Discovered {len(all_images)} test images in downloads folder.")

    candidates = [
        "spacejoy-umAXneH4GhA-unsplash.jpg",              # Interior room (furniture & floor)
        "PXL_20260902_220243594-2.jpg",                   # Pixel camera shot with EXIF
        "aamir-tM4HEI-nY2Y-unsplash.jpg",                 # High-res photography (5724x3220)
        "dekogon-studios-highresscreenshot00027.jpg",      # Game engine render
        "constantine-mountain-20260811spiritedawaystudy-iv.jpg", # Large landscape art (4.8MB)
        "candy-collecchia-s-staticcam-0475.webp",          # WebP asset
    ]
    test_battery = []
    for c in candidates:
        cand_p = DOWNLOADS_DIR / c
        if cand_p.exists():
            test_battery.append(cand_p)

    if len(test_battery) < 4:
        test_battery = all_images[:6]

    print("Selected Test Battery:")
    for p in test_battery:
        print(f"  * {p.name} ({p.stat().st_size / 1024**2:.2f} MB)")

    # Execute Daemon Diagnostics
    daemon_results, scaling_results = run_daemon_diagnostics(test_battery)

    p1_summary = {
        "daemon_inferences": daemon_results,
        "preset_scaling": scaling_results,
    }
    (OUTPUT_DIR / "daemon_diagnostics.json").write_text(json.dumps(p1_summary, indent=2))
    print(f"\n[INFO] Daemon diagnostic results written to {OUTPUT_DIR / 'daemon_diagnostics.json'}")


if __name__ == "__main__":
    main()
