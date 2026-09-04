# MoGe Splat Studio 2.1 — Amended Build Spec (Supersedes v2.0.0)

> Target: Blender 5.2.1 LTS (Python 3.13, numpy 2.3.4) + MoGe venv (Python 3.11, torch 2.11+cu128)
> Hardware: RTX 4070 Ti SUPER 16GB / Ryzen 9 7950X / 64GB DDR5 / Win11
> Repo: `E:\MOGE` (greenfield rebuild, does not modify `mysterious-archimedes\MoGe` upstream)

## What v2.0.0 got right (kept)

- Mesh-vs-splat: Gradio `DepthMap3DViewer(point_scale=1.4)` renders un-indexed splats, not `tri=True` mesh. Blender must do the same.
- Single model (MoGe-3). No StableDelight/PBRify diffusion bloat.
- Cold CLI `subprocess.run(cli_infer.py)` is ~4.5s overhead vs ~0.3-1.5s infer. Warm daemon required.

## What v2.0.0 got wrong (fixed here)

| # | v2.0.0 claim | Reality / bug | Fix in 2.1 |
|---|--------------|---------------|------------|
| 1 | `<=500ms` roundtrip, `<=3.5GB` VRAM | High/1536px+refine3 on 4070TiS is 0.8-2.5s warm; Blender+Eevee+2M pts is 6-9GB total | Acceptance: `<=2.5s warm Balanced, <=6s cold`, `<=9GB total` (still safe on 16GB) |
| 2 | `foreach_set("co")` + `BYTE_COLOR foreach_set(color, uint8)` | BYTE_COLOR expects float32 RGBA x4, not uint8 RGB x3. Code as-written fails/mistints | Use `FLOAT_COLOR` + RGBA float32, tested snippet in extension |
| 3 | Fixed radius `0.015m`, 2M points | Kills viewport (<10fps), holes at distance / blobs up close | Adaptive radius `median_depth / fx_px * 1.4`, cap 1.2M pts w/ stride downsample, user slider |
| 4 | `CompositorNodeComposite -> NodeGroupOutput` rename | Wrong: GroupOutput is for node *groups*, scene still needs Composite+Viewer | Try Composite first, fallback GroupOutput (matches existing fallback factory) |
| 5 | `resolution Ultra=30` | v3 `infer()` maps `num_tokens = 1200+(level/9)*2400`; 30 = 9200 tokens, OOM | Clamp 0-9. Presets: Draft Low/1024/refine1, Balanced High/1536/refine2, Quality High/1536/refine3 |
| 6 | `fov_y = fov_x*(h/w)` (`cli_infer.py:114`) | Linear, wrong for wide/portrait | `fov_y = 2*atan(tan(fov_x/2)*h/w)` |
| 7 | Only `depth_map_edge(ltol=0.01)` | Erodes thin structures or leaves curtains | `mask & ~(depth_edge & normal_edge 5deg)` like `moge/scripts/infer.py:141` |
| 8 | `refine_normals` UI wired | Dead: flag defined in `__init__.py:859` + `cli_infer.py:39` but never passed/used upstream | Deprecated in daemon (warn), mapped to Blender Laplacian Smooth option |
| 9 | Hardcoded `C:\Users\Navneeth\...`, manifest v1.0.0 vs `bl_info` v1.2.0 | Breaks portability, Extensions platform reject | `MOGE_REPO` env + addon prefs, single version `2.0.0`, `blender_version_min 4.2.0` |
| 10 | HTTP binary custom struct | Fragile across Py 3.11/3.13 + numpy 2.x | `.npz` (uncompressed) over HTTP: `np.load(BytesIO)` both ends, no manual struct |

## Architecture (built)

```
E:\MOGE\
  daemon/moge_daemon.py      # FastAPI :8766, warm MODELS{}, /health + /infer -> .npz
  daemon/launch_daemon.bat   # uses MoGe .venv python + uvicorn
  shared/protocol.py         # constants: presets, reso map, fov fix, edge defaults
  blender_extension/moge_splat_studio/
    __init__.py              # 5.2 extension: daemon scan + CLI fallback + splat + relight
    blender_manifest.toml
  tests/                     # no-GPU: protocol/fov/npz roundtrip + py_compile
  tools/install_extension.py # zip + copy to 5.2 extensions dir
```

- Daemon input: JPEG/PNG bytes + `model_version v3/v2/v1`, `resolution_level Low/Medium/High`, `refine_steps`, `max_size`, `seamless/apply_mask/remove_edges`, optional `fov_x`.
- Daemon output `.npz`: `points (H,W,3 f32 OpenCV x-right y-down z-forward)`, `depth (H,W f32)`, `normal (H,W,3 f32, zeros if none)`, `mask (H,W bool)`, `intrinsics (3,3 f32 normalized)`, `image (H,W,3 u8 resized RGB)`, `fov_x, fov_y, width, height`.
- Blender converts `points -> [x, z, -y]` (matches `cli_infer.py:117`), flattens valid mask, stride-caps, injects via `foreach_set` with undo off + viewport hidden.
- Geometry Nodes: `Mesh to Points -> Set Point Radius (adaptive) -> Set Material`. Material: Principled Metallic 0, Roughness 0.8, Vertex Color -> Base Color. Eevee-compatible (instancing path noted for future icosphere option).
- Compositor relight: Source Plate + Normal Pass (Non-Color) + `CompositorNodeNormal` gizmo -> MixRGB Multiply -> Separate -> Add+Add -> Maximum(0) -> * LightColor * Power + Ambient -> * Plate -> Composite + Viewer. Bound to `scene.compositing_node_group` with fallback to `node_tree`, attached to all NODE_EDITOR spaces. Stale cache fixed via `last_scanned_image` + `.reload()`.

## Acceptance (realistic)

1. Fidelity: splat view matches Gradio (no curtains/faceting), Smart interpolation.
2. Latency warm: Draft <=1.2s, Balanced <=2.5s on 4070TiS. Cold CLI <=6s.
3. VRAM total <=9GB (daemon ~2.5-3.5GB + Blender).
4. Zero RNA errors on 5.2.1, no silent dead options.
5. No extra diffusion models, localhost-only, no cloud.

## 2.2 Decoupled full-res color (shipped)

Geometry runs at infer size (1536 default); vertex colors are sampled from the native source file via per-axis nearest mapping (infer_to_orig_coords, canonical in shared/protocol.py, vendored in addon). Measured on games-artist-image-01b.jpg @1536: Laplacian var 406 -> 2192 (5.4x), grad energy 130 -> 245, PSNR-vs-native 30.3dB -> identical. Toggle Full-res color (default ON); zero VRAM/payload cost; falls back to infer colors if the file is missing. Daemon also emits orig_width/orig_height (ignored by old clients).


## 2.3 Per-point adaptive radius (shipped)

One global radius is always wrong somewhere (footprint = depth/fx). Scan now stores SplatDepth + SplatRadius (FLOAT POINT) and fx on the object; MoGe_Splat_Viewer_v2 reads radius from the attribute with a 2mm floor fallback (legacy meshes stay visible). Examples @fx=1000: 4m -> 5.6mm, 48m -> 67mm. Uniform override preserved via Splat radius > 0; Adaptive scale 0.2-3.0 rewrites the attribute exactly (no drift). v1 group untouched so old files render as before.


## 2.4 Daemon auto-start (shipped)

Scan classifies :8766 first: ok -> infer; refused -> spawn MoGe venv detached (logs to temp/moge_daemon.log, pid to temp/moge_daemon.pid), poll /health up to 120s, then infer (first boot ~10s incl. v3 load); conflict (e.g. another app, HTTP 404) -> hard error, never auto-start over a foreign port. Timeout leaves the process (covers first-ever HF download); next Scan finds it up. Stop button taskkills the recorded pid. Auto-start toggle + python override in panel; MOGE_HOME/MOGE_PY/MOGE_DAEMON_PORT envs respected. Tested headless vs fake server (ok/refused/conflict-safe), cmd shape, home resolution, real kill of a sleeper pid.


## 2.5 Grid levelling (shipped)

Floor -> z=0 via parent Empty MoGe_Level (raw splat/camera data never touched; Remove restores camera-space exactly). Auto: daemon POST /level with cached response.npz -> shared/floor.py RANSAC (signed-normal-gated so ceilings can't win, up-cone 40deg, 1500 iters on <=60k subsample, SVD refit, median recenter) -> 4x4 Blender-space matrix. Measured: synthetic flat/20deg rooms zeroed to <0.005 with det-1 rotations; real 2M-pt street scan fits in 0.35s. Confidence honesty: <15% inliers still applies but warns (verified: 8.7% street scene flags correctly while plane stays stable across tolerance sweeps). Manual: Add floor markers (A/B/C in front of camera) -> Level to markers (SVD, collinear rejected, works in raw space even when already levelled). Fine-tune by transforming the Empty directly.


## 2.6 Relight black-screen fix (shipped)

Root causes on Blender 5.2.1 (all legacy CompositorNode* math/mix/composite types are gone from RNA): (1) unified ShaderNodeMix exposes TWO Factor sockets, so index wiring fed normals into Factor and left B black; fixed with socket-exact wiring (Factor[0], color A[6]/B[7], Result color). (2) Scene output went to a virtual Group-Output socket leaving Render Result empty; fixed by creating the Image interface socket first. (3) normal.png ([0,1]) was never remapped to [-1,1]; now Math-only remap (SUBTRACT 0.5 / MULTIPLY 2.0 per channel, skipped for raw .exr). Verified by render-to-file: Viewer-equivalent output went from [0,0,0] to plate mean (0.67,0.22,0.17) with directional halves R 0.85 (+Z-facing) vs 0.49 (sideways). Operator now self-checks for virtual links. Old .blend files must re-run Setup relighter once.


## 2.7 Giant backbone (shipped, opt-in)

Ruicheng/moge-3-vitg (5GB weights) measured head-to-head vs vitl @1536/High/r3: warmed infer 0.48s vs 0.29s, peak VRAM 7.3GB vs 2.7GB, load 10s vs 3.5s, geometry proxies identical (sharpness, inlier 4.4 vs 4.5%, tilt within 0.2deg, normal fields agree median 7.4deg). Verdict: same quality on typical shots, 2.7x memory. Daemon takes variant=vitl|vitg (default vitl, old clients unaffected); one v3 variant resident at a time with logged eviction (verified live both directions, no leak: 5.06GB <-> 1.50GB). Blender Giant preset stamps variant=vitg (no extra panel row). First Giant scan pays ~10s load once.


## 2.8 Push limits: TTA + EXIF FOV + crop-zoom + meta viewer + passepartout (shipped)

TTA: /infer tta=off/flip/flip3. flip = mirror pair, mean-fused (cancels mirror bias, halves jitter); flip3 adds a 0.8x view for true-median outlier rejection (shared/tta.py, numpy-only, tested). Measured: slight denoise direction, edge frac 0.0174 -> 0.0160. 2-3x time. Default off.

EXIF: 35mm-equiv focal (nested sub-IFD aware) feeds model.infer(fov_x=...) so geometry itself improves; fov_src manual/exif/model recorded in npz+meta. Verified live: Pixel photo 73.74deg direct == daemon.

Crop-zoom: /zoom endpoint infers a native crop with crop-correct focal (normalized-K math in shared/zoom.py) and returns points in the PARENT frame; Blender drops parent footprint pixels and merges pre-build (own radii via zoom fx, native colors via crop-rect mapping, 500k zoom cap). Caught by test: wrong focal (K00*crop_w) gave 62% seam; fixed formula gives 8.6% median boundary seam (0.2% best side), verified live on the 4K phone photo (1075px crop -> 1.16M dense pts).

Meta viewer: box 6 renders last-scan meta.json via shared/meta.py (panel vendors a parity-tested copy). Level ops stamp/clear the level record. Camera: passepartout_alpha=1.0 + show on every scan.


## 2.9 Panorama rooms (shipped)

POST /pano: equirect (2:1 checked) -> 8 yaw tangent faces + top/bottom poles at forced 90deg FOV (shared/pano.py gnomonic extraction, numpy bilinear fallback) -> per-face infer -> loop-closed scale solve (side area overlaps weight 1, pole boundary rings 0.25, mean-log gauge) -> merged flat cloud in pano frame + yaw/pitch rig spec. Payload: points/colors/normals/depths/face_id flat + scales + fit residuals. Measured live on 15520px Osmo file: 10 faces x ~2s, scales 0.87-1.07, pre 3.8% -> post 1.8% residual, 867k splats + 10 rigged cameras. Blender Scan 360 Room builds via the shared mesh builder (+PanoFace attr), rig parent, optional auto-level (works: /level accepts flat clouds). Sign-convention audit fixed three coordinated bugs (CV y-down: Rx pitch signs, equirect elevation sign, pole band sides; rig basis rebuilt right-handed after a det -1 reflection slipped through).


## 2.10 Pano redesign: exclusive wedges + per-face objects (shipped)

User report: merged 10-face cloud showed 3-4x ghosts. Diagnosis (measured, not guessed): fit medians agreed (post 1.8%) but border pixels disagreed 13-24% -- MoGe bows geometry at 90deg-FOV borders, so overlapping wedges doubled. Fix by construction: daemon scans wide (overlap kept for the scale solve) but outputs exclusive sectors (sides |yaw|<=22.8deg, poles cap 45.5deg; shared/pano.py masks, tested tiling). No rendered overlap exists, so doubling is impossible. Blender builds one object per face (MoGe_Pano_Fxx, camera-local coords) parented to its rig camera, each pair in its own Pano Fxx collection for per-side toggles; rig levels as one assembly; Apply-radius accepts any face object. Boundary handoff stat (post-scale adjacent-column agreement) reported per scan: 7.6% live (border pixels are the most distorted; centers agree ~2%). Live full-pano: 10 faces/collections/cams, 750k splats, world-preserved through parenting (tested).

