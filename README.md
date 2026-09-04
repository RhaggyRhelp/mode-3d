# MoDe 3D Studio

[![Blender](https://img.shields.io/badge/Blender-4.2%20%7C%205.x-orange.svg)](https://www.blender.org/)
[![Python](https://img.shields.io/badge/Python-3.10%20%7C%203.11%20%7C%203.12%20%7C%203.13-blue.svg)](https://www.python.org/)
[![PyTorch](https://img.shields.io/badge/PyTorch-2.1+-ee4c2c.svg)](https://pytorch.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

**MoDe 3D Studio** (Metric Monocular Depth Engine) is a high-performance 3D depth and relighting studio for Blender. It connects Blender to a warm GPU daemon powered by **Microsoft MoGe-3**, turning single photographs into metric 3D point-splats, accurate camera setups, and relightable compositing graphs in ~1–2 seconds.

---

## Key Features

* **Warm GPU Daemon Architecture:** Keeps MoGe-3 loaded in VRAM for instant, low-latency scanning (~1.2s to 2.5s) without cold Python process startup penalties.
* **Metric Point Splats (Zero Faceting):** Uses procedural Geometry Nodes to instance smooth screen-space splats or oriented Gaussian surfels. Eliminates the jagged polygon curtains and tearing typical of naive triangulated depth meshes.
* **Per-Point Adaptive Radius:** Computes individual splat radii based on physical metric depth and camera focal length ($r \propto Z/f$), ensuring dense near-field coverage while preventing far-field blobbing.
* **Decoupled Full-Resolution Color:** Samples vertex colors directly from the native camera photograph while running the geometric vision backbone at an optimal token resolution.
* **Ground Grid Levelling:** Detects physical floor planes via signed-normal RANSAC estimation and aligns the room to Blender's ground grid ($Z=0$) via a parent transformation Empty.
* **2.5D Compositor Relighter:** Builds a real-time normal-pass relighting graph in Blender's Compositor. Adjust the lighting angle, color, and intensity directly with an interactive 3D normal gizmo.
* **Self-Cleaning Runtime (Zero Accumulation):** Automatically purges previous scan payloads on every new scan. Includes an in-Blender button to scrub both disk caches and unreferenced Blender datablocks.

---

## Architecture Overview

```
Single Image (.jpg/.png/.webp)
              │
              ▼
   ┌──────────────────────┐
   │   MoGe GPU Daemon    │  (FastAPI :8766 - Warm VRAM)
   │   MoGe-3 ViT-L/G     │  Estimates: metric points, depth, normals, FOV
   └──────────┬───────────┘
              │ (Streaming uncompressed .npz over localhost)
              ▼
   ┌──────────────────────┐
   │  Blender Extension   │  (Blender 4.2+ / 5.x)
   │  - Geometry Nodes    │  Adaptive point splats / Gaussian surfels
   │  - Metric Camera     │  Physical focal length & sensor match
   │  - Compositor Tree   │  Interactive 2.5D normal-gizmo relighter
   │  - Floor Leveller    │  RANSAC floor alignment to Z=0
   │  - Cache Purger      │  Zero-accumulation temp file management
   └──────────────────────┘
```

---

## Quick Start Guide

### 1. Set Up Python Environment (Daemon)

Ensure you have Python 3.10+ and a CUDA-capable GPU. Clone this repository and install dependencies:

```bash
# Clone the repository
git clone https://github.com/RhaggyRhelp/mode-3d.git
cd mode-3d

# Create and activate a virtual environment
python -m venv .venv
# On Windows:
.venv\Scripts\activate
# On Linux/macOS:
source .venv/bin/activate

# Install PyTorch with CUDA support (example for CUDA 12.1+):
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121

# Install daemon dependencies
pip install -r requirements.txt
```

> **Note on MoGe:** If `moge` is not installed as a package, clone the upstream [Microsoft MoGe](https://github.com/microsoft/MoGe) repository alongside this project or set the `MOGE_REPO` environment variable.

---

### 2. Start the GPU Daemon

Launch the warm daemon:

* **Windows:** Double-click `daemon/launch_daemon.bat`, or run:
  ```bash
  python daemon/launch_daemon.py
  ```
* **Linux / macOS:**
  ```bash
  python daemon/launch_daemon.py
  ```

Check health in your browser: `http://127.0.0.1:8766/health`

---

### 3. Install the Blender Extension

Run the cross-platform packaging script to stage the extension directly into your local Blender:

```bash
python tools/install_extension.py
```

Then in Blender (version 4.2 LTS or 5.x):
1. Open **Edit > Preferences > Extensions** (or Add-ons).
2. Enable **MoDe 3D Studio**.
3. In the 3D Viewport, press `N` to open the sidebar and navigate to the **MoDe 3D** tab.

*(Alternatively, you can drag the built `.zip` from `dist/moge_splat_studio.zip` onto Blender and choose "Install from Disk".)*

---

## Recommended Presets & Hardware

| Preset | Target Hardware | Time | Description |
| :--- | :--- | :---: | :--- |
| **Draft** | 6GB – 8GB VRAM | ~0.8s | MoGe-2, Low detail, 1024px. Ideal for fast camera matching and layout previews. |
| **Balanced (Recommended)** | 8GB – 12GB VRAM | ~1.8s | MoGe-3 ViT-L, High detail, 2 Refine passes, 1536px. Optimal balance of speed and detail. |
| **Quality** | 12GB – 16GB VRAM | ~2.5s | MoGe-3 ViT-L, High detail, 3 Refine passes, 1536px. Sharper surface boundaries. |
| **Giant** | 16GB+ VRAM | ~3.5s | MoGe-3 ViT-G (5GB weights), 1536px. Maximum depth accuracy for hero assets. |
| **Max Quality** | 16GB+ VRAM | ~5.0s | MoGe-3 ViT-G, 4096px, 7 Refine passes, Flip x2 TTA, 4M point budget. |

---

## Storage & Self-Cleaning

MoGe Splat Studio is engineered to prevent junk accumulation:
* **Single-Session Retention:** All temporary `.npz` arrays, plate textures, and diagnostic records are strictly stored in an isolated directory (`<tempdir>/moge_splat_studio_cache/active/`).
* **Auto-Purge on New Scans:** Starting a new scan automatically cleans up previous temporary payloads.
* **One-Click Purge:** Click **Purge Cache** in the sidebar panel to immediately delete temporary files from disk and remove unreferenced MoGe meshes, materials, and node groups from your `.blend` file.

---

## Testing & Verification

Run the test suite to verify mathematics, protocol definitions, and headless Blender integration:

```bash
# Run unit tests (CPU-only, mock data)
python tests/test_protocol.py
python tests/test_adaptive_radius.py
python tests/test_decouple.py
python tests/test_floor.py
python tests/test_push.py

# Run headless Blender registration test
blender --factory-startup --background --python tools/test_headless_blender.py
```

---

## Citations & Acknowledgements

MoGe Splat Studio builds upon research in monocular geometry estimation developed by **Microsoft Research** and **HKUST**:

* **Ruicheng Wang, Shengyi Qian, Angela Dai, Xiaolong Wang** — *MoGe: Unlocking Open-Domain Monocular Geometry Estimation* (CVPR 2024).
* **Ruicheng Wang, Shengyi Qian, Angela Dai, Xiaolong Wang** — *MoGe-2: Accurate Metric Monocular Geometry Estimation* (NeurIPS 2024).
* **Ruicheng Wang, Shengyi Qian, Angela Dai, Xiaolong Wang** — *MoGe-3: Self-Guided Sparse Volumetric Refinement for Fine-Grained Monocular 3D* (2025).

See [docs/CITATIONS.md](docs/CITATIONS.md) for complete BibTeX entries.

---

## License

This project is licensed under the [MIT License](LICENSE).
