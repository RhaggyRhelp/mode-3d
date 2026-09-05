# MoDe 3D Studio

<div align="center">

[![Blender 4.2 | 5.2](https://img.shields.io/badge/Blender-4.2%20LTS%20%7C%205.2-orange.svg?logo=blender&logoColor=white)](https://www.blender.org/)
[![Python 3.10-3.12](https://img.shields.io/badge/Python-3.10%20%7C%203.11%20%7C%203.12-blue.svg?logo=python&logoColor=white)](https://www.python.org/)
[![PyTorch CUDA](https://img.shields.io/badge/PyTorch-2.1+%20CUDA-ee4c2c.svg?logo=pytorch&logoColor=white)](https://pytorch.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![GitHub Pages](https://img.shields.io/badge/Website-Live%20Docs%20%26%20Demo-00f0ff.svg)](https://RhaggyRhelp.github.io/mode-3d/)

**Single Photo In. Metric 3D Splats Out. Real-Time Relighting in Blender.**

[🌐 **Interactive Website & Live Demo**](https://RhaggyRhelp.github.io/mode-3d/) • [📖 **Philosophy & Flow State**](docs/PHILOSOPHY.md) • [📚 **Complete User Manual**](docs/USER_MANUAL.md) • [📦 **Releases**](https://github.com/RhaggyRhelp/mode-3d/releases)

---

</div>

**MoDe 3D Studio** (Metric Monocular Depth Engine) is a fast, artist-friendly 3D reconstruction and relighting studio for Blender. Powered by **Microsoft MoGe-3** running in a warm GPU daemon, it transforms any single 2D photograph into millimeter-accurate 3D point splats, matched camera projections, and a live 2.5D normal relighter in **~1.2 to 2.0 seconds**.

Zero polygon tearing. Zero ragged curtain artifacts. Pure creative flow state.

---

## 🌟 Key Highlights

* ⚡ **Warm GPU Daemon (~1.2s to 2.5s):** Keeps MoGe-3 loaded in VRAM via a local FastAPI server (`:8766`). Scan photos continuously with zero cold-start process overhead.
* 🎯 **Metric Point Splats (Zero Faceting):** Procedural Geometry Nodes instance smooth screen-space splats or oriented Gaussian surfels, eliminating the jagged polygon curtains typical of naive triangulated depth meshes.
* 🔍 **Per-Point Adaptive Radius:** Computes physical splat radii from depth and camera focal length ($r \propto Z/f$). Ensures dense near-field coverage while preventing far-field blobbing.
* 🎨 **Decoupled Native-Resolution Color:** Runs the geometric vision backbone at optimal token density while sampling vertex colors directly from your native 4K+ camera photograph.
* 📐 **Instant Floor Levelling ($Z=0$):** RANSAC signed-normal plane detection aligns the room's physical ground to Blender's floor grid automatically via a parent Empty.
* 💡 **2.5D Compositor Relighter:** Automatically generates a real-time normal-pass relighting graph in Blender's Compositor with an interactive 3D normal gizmo in the 3D Viewport.
* 🧹 **Zero-Accumulation Runtime:** Automatically clears previous scan arrays on each new run. Includes a 1-click **Purge Cache** button to delete temporary disk arrays and purge unused Blender datablocks.

---

## 🏗️ Architecture

```
Single Photo (.jpg / .png / .webp)
              │
              ▼
   ┌──────────────────────┐
   │   MoGe GPU Daemon    │  (FastAPI :8766 - Warm in VRAM)
   │   MoGe-3 ViT-L/G     │  Estimates: metric points, depth, normals, FOV
   └──────────┬───────────┘
              │ (Streaming uncompressed .npz over localhost)
              ▼
   ┌──────────────────────┐
   │  Blender Extension   │  (Blender 4.2+ / 5.2 LTS)
   │  - Geometry Nodes    │  Adaptive point splats / Gaussian surfels
   │  - Metric Camera     │  Physical focal length & sensor match
   │  - Compositor Tree   │  Interactive 2.5D normal-gizmo relighter
   │  - Floor Leveller    │  RANSAC floor alignment to Z=0
   │  - Cache Purger      │  Zero-accumulation temp file management
   └──────────────────────┘
```

---

## 🚀 Quick Start Guide

### 🎨 Artist Workflow (Zero-Terminal, 1-Click Setup)

No command-line or Python knowledge required!

1. **Clone or Download** this repository.
2. **Run the One-Click Launcher:**
   * **Windows:** Double-click **`Start_MoDe_3D.bat`**
   * **Linux / macOS:** Run **`./Start_MoDe_3D.sh`**
   
   *The launcher automatically configures an isolated `.venv`, installs PyTorch with CUDA acceleration (`cu128` with `cu121` fallback), fetches MoGe-3, packages the extension, and **auto-stages it directly into your Blender installation**!*

3. **In Blender (4.2+ or 5.2):**
   * Go to **Edit > Preferences > Extensions** (or Add-ons).
   * Enable **MoDe 3D Studio** *(it will already appear in your list!)*.
   * In the 3D Viewport, press `N` to open the sidebar and switch to the **MoDe 3D** tab.
   * Select your photo and click **Generate 3D Splats**!

*(Alternatively, you can drag the built `dist/moge_splat_studio.zip` directly onto Blender and choose "Install from Disk".)*

<details>
<summary><b>Launcher Command-Line Flags (Optional)</b></summary>

* `Start_MoDe_3D.bat --no-launch` — Install and stage extension only, without starting the daemon (Blender will start it on demand).
* `Start_MoDe_3D.bat --check` — Test environment (Python, venv, daemon health) and exit.
* `Start_MoDe_3D.bat --uninstall` — Cleanly remove staged extension, configs, and shortcuts.
</details>

---

### 💻 Developer Workflow (Manual Setup)

<details>
<summary><b>Click to expand manual setup instructions</b></summary>

```bash
# 1. Create and activate virtual environment (Python 3.10–3.12 recommended)
python -m venv .venv
# Windows:
.venv\Scripts\activate
# Linux/macOS:
source .venv/bin/activate

# 2. Install PyTorch with CUDA acceleration
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu128

# 3. Install daemon dependencies
pip install -r requirements.txt

# 4. Package and stage extension to local Blender
python tools/install_extension.py

# 5. Launch the warm GPU daemon
python daemon/launch_daemon.py
```

Verify daemon status in your browser at `http://127.0.0.1:8766/health`.
</details>

---

## ⚡ Presets & Hardware Guide

| Preset | Target GPU | Scan Time | Recommended Use Case |
| :--- | :--- | :---: | :--- |
| **Draft** | 6GB – 8GB VRAM | **~0.6s** | MoGe-3 ViT-L, 1024px, 0 Refine passes. Instant camera FOV matching and rough depth blockout. |
| **Balanced** *(Recommended)* | 8GB – 12GB VRAM | **~1.8s** | MoGe-3 ViT-L, 1536px, 2 Refine passes. The optimal sweet spot between speed and surface detail. |
| **Quality** | 12GB – 16GB VRAM | **~3.2s** | MoGe-3 ViT-L, 2448px, 3 Refine passes. Sharper edges, architectural lines, and thin structures. |
| **Max Quality** | 16GB+ VRAM | **~5.5s** | Giant MoGe-3 ViT-G (5GB), 4096px, 7 Passes, Flip x2 Anti-Jitter, 4M point budget. Hero-shot fidelity. |

---

## 🧼 Storage & Self-Cleaning

MoDe 3D Studio is built to keep your system clean:
* **Isolated Cache:** All temporary `.npz` arrays, camera plates, and logs are isolated inside `<tempdir>/moge_splat_studio_cache/active/`.
* **Auto-Purge:** Starting a new scan automatically cleans previous temp files.
* **One-Click Purge:** The **Purge Cache** sidebar button deletes disk cache files and purges unreferenced Blender meshes, node groups, and materials from your `.blend` file.

---

## 🧪 Testing & Verification

Run the test suite to verify math, protocol compatibility, and headless Blender registration:

```bash
# Pure-numpy protocol & unit tests (CPU-only)
python -m pytest tests/test_protocol.py tests/test_push.py tests/test_floor.py -q

# Multi-tier health verification (hygiene, daemon, ports)
python tools/health_check.py

# Headless Blender verification (Blender 4.2 / 5.2)
blender --factory-startup --background --python tools/test_headless_blender.py
```

---

## ❓ Troubleshooting

* **Port 8766 in use:** Setup detects existing daemons automatically. If you have an old process running, click **Stop AI Engine** in the sidebar or terminate port 8766.
* **Windows Firewall prompt:** The daemon binds to `127.0.0.1` (localhost only). Allow the loopback connection; no data ever leaves your computer.
* **Giant ViT-G memory usage:** ViT-G requires ~7GB VRAM. If running low on GPU memory, choose **Balanced** or close external VRAM-heavy apps.
* **Non-blocking execution:** In v2.2+, scans run asynchronously with progress indicators and cooperative `ESC` cancellation.

---

## 📚 Citations & Research

MoDe 3D Studio builds upon breakthrough monocular geometry estimation research by **Microsoft Research** and **HKUST**:

```bibtex
@inproceedings{wang2024moge,
  title={MoGe: Unlocking Open-Domain Monocular Geometry Estimation},
  author={Wang, Ruicheng and Qian, Shengyi and Dai, Angela and Wang, Xiaolong},
  booktitle={CVPR},
  year={2024}
}
@article{wang2024moge2,
  title={MoGe-2: Accurate Metric Monocular Geometry Estimation},
  author={Wang, Ruicheng and Qian, Shengyi and Dai, Angela and Wang, Xiaolong},
  journal={arXiv:2410.19115},
  year={2024}
}
@article{wang2025moge3,
  title={MoGe-3: Self-Guided Sparse Volumetric Refinement for Fine-Grained Monocular 3D},
  author={Wang, Ruicheng and Qian, Shengyi and Dai, Angela and Wang, Xiaolong},
  journal={arXiv},
  year={2025}
}
```

See [`docs/CITATIONS.md`](docs/CITATIONS.md) for further details.

---

## 📄 License

This project is licensed under the [MIT License](LICENSE).
