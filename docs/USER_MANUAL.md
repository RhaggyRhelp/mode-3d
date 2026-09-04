# MoGe Splat Studio — Complete User Manual & Settings Guide

> **Quick Summary:** MoGe Splat Studio turns single photos into metric 3D point-splats and camera setups inside Blender using a fast, warm GPU daemon. This guide details every setting, toggle, and button so you know exactly what to change, how much it impacts quality and speed, and which option fits your workflow.

---

## Table of Contents
1. [The 30-Second "Cheat Sheet" (Which Preset for What?)](#1-the-30-second-cheat-sheet)
2. [Section 1: Source Image & Daemon Controls](#2-source-image--daemon-controls)
3. [Section 2: Quality & Inference Settings](#3-quality--inference-settings)
4. [Section 3: Surface & Masking Modes](#4-surface--masking-modes)
5. [Section 4: Field of View (FOV) & Camera Settings](#5-field-of-view-fov--camera-settings)
6. [Section 5: Dot Size & Viewport Display](#6-dot-size--viewport-display)
7. [Section 6: 2.5D Compositor Relighter](#7-25d-compositor-relighter)
8. [Section 7: Grid Levelling (Aligning Floor to Z=0)](#8-grid-levelling-aligning-floor-to-z0)
9. [Section 8: Diagnostic Metadata Viewer](#9-diagnostic-metadata-viewer)
10. [Troubleshooting Visual Artifacts](#10-troubleshooting-visual-artifacts)

---

## 1. The 30-Second "Cheat Sheet"

If you don't want to tweak 15 sliders, pick one of these four setups:

| Goal / Scenario | Recommended Settings | Scan Time | What You Get |
| :--- | :--- | :--- | :--- |
| **Rapid Previews & Camera Matching** | Preset: **Draft**<br>Surface: **Seamless** | **~0.6s** | Fast sub-second camera FOV alignment and rough depth shapes. Great for quickly checking if a photo works. |
| **Interior Rooms & Architecture** | Preset: **Balanced**<br>Surface: **Seamless**<br>Auto Level: **Level floor (auto)** | **~1.5 – 2.0s** | Watertight walls and floors without holes. Floor aligned cleanly to the Blender ground grid ($Z=0$). |
| **Characters, Props & Furniture** | Preset: **Balanced** or **Quality**<br>Surface: **Split islands**<br>Mask sky/void: **ON** | **~2.0 – 3.2s** | Cuts out background "spiderweb curtains" and keeps edges clean and isolated. |
| **Hero Shots & Hairline Details** | Preset: **Quality**<br>TTA Ensemble: **Flip x2**<br>Full-Res Color: **ON** | **~4.0 – 5.5s** | Denoised, jitter-free geometric depth with native camera texture sharpness. |
| **Extreme All-Out Max Quality** | Preset: **Max Quality (Giant 4K)**<br>Surface: **Seamless** or **Split islands** | **~5.5 – 7.0s** | **The Ultimate Quality Bundle**: Giant ViT-G (5GB) backbone + 4096px resolution + 7 Refine passes + Flip x2 Anti-Jitter + 4,000,000 point budget! |

---

## 2. Simple Mode vs. Advanced Mode

At the very top of the sidebar panel, a segmented switcher lets you toggle between:

* **Simple Mode (Default):** Streamlined, clutter-free workflow. Exposes only the essential controls: Pick Image, Preset, Surface Mode, and the large **Scan -> Splats** button. Once scanned, quick one-click shortcuts appear for **Camera**, **Level Floor**, and **Relight**.
* **Advanced Mode:** Unfolds the full studio interface with all fine-grained sliders, daemon management, dot-size multipliers, point budgets up to 12M, and real-time metadata diagnostics.

---

## 3. Source Image & Daemon Controls

Located at the very top of the **MoGe Splat** sidebar panel.

### Source Image (`import_path`)
* **What it does:** Selects the input image file (.jpg, .png, .webp, .bmp, .tiff).
* **What changing it does:** Changes the base image used for 3D reconstruction.
* **Pro-tip:** If your photo came from a modern smartphone or DSLR, keep the raw file! MoGe Splat Studio automatically extracts camera EXIF focal lengths to compute physically accurate camera FOV.

---

### Check GPU Daemon (`moge_splat.ensure_daemon`)
* **What it does:** Pings the background Python AI server (`http://127.0.0.1:8766/health`) to confirm that the GPU is ready and shows which model checkpoint is loaded in VRAM.
* **When to use:** Click if you want to verify that your GPU is online before running a large batch.

---

### Auto-start Daemon (`daemon_autostart`)
* **What it does:** When enabled (**ON** by default), clicking **Scan -> Splats** will automatically launch the MoGe daemon in the background if it is not already running.
* **Impact:** 
  * **First scan after boot:** Takes ~10 seconds while the model loads into VRAM.
  * **Subsequent scans:** Instant warm response (~1–2 seconds).
* **When to change:** Keep **ON**. Only turn OFF if you prefer managing the daemon manually via `launch_daemon.bat` or a remote server.

---

### Stop Daemon (`moge_splat.stop_daemon`)
* **What it does:** Terminates the background Python daemon process and immediately frees up GPU VRAM (saving ~2.5 GB – 7.3 GB of video memory).
* **When to use:** When you are done scanning and want all your VRAM back for heavy Blender rendering, simulations, or gaming.

---

## 3. Quality & Inference Settings

These controls govern the neural network inference pass that extracts 3D depth and surface normals.

```
+-------------------------------------------------------------------------------+
| SETTINGS HIERARCHY:                                                           |
| Preset (Macro) ---> Resolution (1536/2448/4096) + Iterations (0-7) + Detail   |
+-------------------------------------------------------------------------------+
```

### Preset (`preset`)
* **What it does:** Pre-configures all underlying neural network parameters with tested, optimal ratios.
* **Options:**
  * **Draft (Fast <1.0s):** Uses **MoGe-3 Standard**, Low feature separation, 0 iterations, 1024px resolution.
    * *Best for:* Sub-second rapid thumbnail scrub, checking camera placement without model swapping.
  * **Balanced (Recommended):** Uses **MoGe-3 Standard**, High feature separation, 2 iterations, 1536px resolution.
    * *Best for:* 90% of real work. Balances crisp geometry, clean surface boundaries, and ~1.8s speed.
  * **Quality (2.5K Crisp):** Uses **MoGe-3 Standard**, High feature separation, 3 iterations, 2448px resolution.
    * *Best for:* High-resolution scenes where fine edges and micro-creases matter (~3.2s).
  * **Max Quality (4K Hero):** All-out hero quality bundle. Uses **MoGe-3 Giant (7GB)**, 4096px resolution, 7 iterations, 2x Anti-Jitter, and 4M point budget.
    * *Best for:* Ultimate hero renders where every hairline crease, wire, and micro-silhouette counts.
  * **Custom:** Automatically activates if you manually alter any fine-grained settings.

---

### Geometry Iterations (`refine_steps`)
* **What it does:** The number of iterative 3D self-refinement passes MoGe-3 performs on its own output field.
* **Range:** `0` to `7` (Default: `2`, Maximum: `7`).
* **Impact on Output:**
  * **0:** Raw draft shape (fastest, but may exhibit slight curvature or wavy walls).
  * **1 – 2 (Sweet Spot):** Flattens walls, straightens structural perspective lines, and eliminates surface ripples.
  * **3:** Extra crispness on complex occlusion boundaries and thin silhouettes.
  * **4 – 7 (Max Convergence):** Maximum geometric alignment. Straightens long architecture lines and sharpens micro-silhouettes to perfection.
* **Recommendation:** **2** for general work; **3** for hero props; **7** for Max Quality.

---

### Scan Resolution (`max_size`)
* **What it does:** Long-edge pixel dimension for 3D point generation.
* **Quick Tiers:**
  * **1536 (Standard):** Fast transfer (~2s), lightweight memory footprint, smooth viewport.
  * **2448 (2.5K Sharp):** High-density intermediate tier (~3.5s). Native 8MP photo sensor ratio, crisp micro-surfaces.
  * **4096 (4K Hero):** Native 4K dense point grid. Handled smoothly on RTX 4070 Ti SUPER 16GB.
  * *(Custom input allows any value between 512 and 4096 px).*
* **Recommendation:** Keep at **1536** for general staging; switch to **2448** or **4096** for hero renders. Note that with *High-Res Source Colors* enabled, texture colors remain 100% sharp from your original photo even at 1536.

---

### Feature Separation (`resolution_level`)
* **What it does:** Controls how finely the AI detects small geometric structures (internally controls Vision Transformer token density).
* **Options:**
  * **Low:** Fewest tokens, fastest, uses lowest GPU memory. Surfaces are slightly rounded.
  * **Medium:** Balanced token density.
  * **High:** Sharpest geometric creases, separating thin objects (table legs, wires, window frames) as distinct 3D geometry rather than blending them into the wall.
* **Recommendation:** Keep on **High** unless running on a low-VRAM GPU (<8 GB).

---

### Anti-Jitter / Denoise Passes (`tta_mode`)
* **What it does:** Multi-pass inference (Test-Time Augmentation). Passes transformed copies of the image through the AI and fuses depth maps to cancel camera sensor noise.
* **Options:**
  * **Off (Single Pass):** Standard single-shot inference (~2s).
  * **2x Mirror Pass (~2x time):** Runs the image normal and horizontally flipped, then averages the two. Cancels out camera bias and cuts random depth jitter in half.
  * **3x Clean Pass (~3x time):** Runs normal, flipped, and an 80% downscaled view. Uses median-voting across all 3 to discard single-pass depth glitches.
* **Recommendation:** Leave **Off** while staging; switch to **2x Mirror** for hero renders.

---

## 4. Surface & Masking Modes

Controls how background skies, edge disocclusions, and object boundaries are filtered.

```
SEAMLESS                     MASKED                       SPLIT ISLANDS
[ Continuous mesh ]          [ Sky / Void Deleted ]       [ Objects Split Apart ]
  ___________                  ___________                  _____     _____
 /           \                /           \                /     \   /     \
/  Foreground \              /  Foreground \              | Obj A | | Obj B |
|  + Sky Wall |              |  (No Sky)   |              \_____/   \_____/
\_____________/              \_____________/
(Watertight, 0 holes)       (Cut horizon/void)            (No background curtains)
```

### Surface Mode (`surface_mode`)

| Mode | What it does | Visual Result | Best For |
| :--- | :--- | :--- | :--- |
| **Seamless (0 holes)** | Retains every valid point without deleting edges. | A completely solid, watertight sheet. Backgrounds connect smoothly to the foreground. | **Indoor rooms, architectural interiors, cave walls, closed environments.** |
| **Masked** | Uses AI segmentation to drop sky and infinite depth voids. | Foreground geometry stays solid; sky and distant horizons are removed. | **Outdoor buildings, street scenes with open skies.** |
| **Split Islands** | Examines depth jumps and normal angle shifts ($>5^\circ$) and severs connecting points. | Objects become isolated floating 3D elements without "stretched spiderweb skin" connecting them to the background. | **Props, isolated products, vehicles, character figures.** |

### Mask sky/void (`apply_mask`)
* *Only visible when Surface is set to **Split Islands**.*
* **What it does:** When checked, cuts out both sharp connecting edges *and* the sky/void regions.

---

## 5. Field of View (FOV) & Camera Settings

### Override FOV (`use_custom_fov`) & HFOV deg (`custom_fov`)
* **What it does:** By default, MoGe automatically reads your camera's EXIF focal length or estimates the FOV using deep learning. Checking this box forces the AI to construct the 3D scene using your exact horizontal field of view.
* **Why it matters:** In MoGe, your custom FOV is passed directly *into* the neural network before depth calculation. It does not simply stretch the camera in Blender—it physically improves depth scale accuracy!
* **Range:** `5.0°` (Telephoto / Zoom lens) to `160.0°` (Extreme Fisheye).
* **When to use:**
  * When you know the focal length (e.g., you rendered a 3D plate at 50mm or shot on a 24mm prime lens).
  * When the automatic FOV estimate feels too flat or overly distorted.

---

## 6. Dot Size & Viewport Display

Found inside collapsible box **3. Dot size & display**.

> [!NOTE]
> MoGe Splat Studio generates **Blender Geometry Nodes Point Sprites** (shaded in real-time by Eevee), NOT un-editable 3D Gaussian Splatting blobs. You can edit them, sculpt them, or light them like normal Blender geometry.

### Uniform radius m (`splat_radius`)
* **What it does:**
  * **If set to `0.0` (Default):** Activates **Adaptive Per-Point Radius**. Every point gets a custom radius based on its camera distance: points close to the camera become tiny and sharp, while points far away expand to fill gaps.
  * **If set to `> 0.0` (e.g. `0.015`):** Forces every single point in the cloud to be identical in size (in meters).
* **Impact:** Setting this to a fixed number makes distant scenery look like a sparse grid of holes ("screen door effect"). Keep it at `0.0`.

---

### Adaptive scale (`radius_scale`)
* **What it does:** A multiplier applied to the adaptive radius calculation.
* **Range:** `0.2` to `3.0` (Default: `1.0`).
* **Visual Result:**
  * **Increase (e.g. 1.3 – 1.6):** Closes holes and gaps in the far distance, creating a smoother solid look.
  * **Decrease (e.g. 0.6 – 0.8):** Makes points sharper and smaller, revealing ultra-fine micro-structures at the cost of tiny pinholes between points.
* **How to update:** Change this slider, then click **Apply radius** to update the viewport immediately without rescanning!

---

### Point budget (`point_budget`)
* **What it does:** The maximum number of points imported into Blender.
* **Default:** `1,200,000` points (Range: 50,000 to 12,000,000).
* **Mechanism:** If the AI outputs 8–11 million points (e.g. from a 4K scan), the add-on applies an even uniform stride downsampler (e.g. taking every 2nd or 3rd point) to meet your budget without clustering or destroying depth structure.
* **Impact on Viewport & Performance:**
  * **1,200,000:** Smooth 60+ FPS navigation in Eevee on RTX 3070/4070+.
  * **4,000,000:** "Retina sweet spot". Point density matches native 4K displays. Smooth 45–60 FPS navigation.
  * **8,000,000 – 12,000,000:** Extreme density for sub-pixel macro inspection. Viewport navigation becomes heavier (~15–25 FPS) and memory overhead increases (~800MB–1GB RAM per mesh).

---

### Full-res color (`fullres_color`)
* **What it does:** **Decoupled High-Resolution Texturing**. Instead of coloring points from the downscaled AI image (1536px), Blender samples the RGB vertex colors directly from your native high-resolution image file on disk (e.g., 4K, 8K, or 12K photo).
* **Impact on Output:** **MASSIVE VISUAL UPGRADE**. Increases texture sharpness by up to 5x with **zero additional GPU VRAM cost**.
* **Recommendation:** Always keep **ON**.

---

### Apply radius Button (`moge_splat.apply_radius`)
* **What it does:** Recalculates and rewrites the `SplatRadius` point attribute across your selected mesh.
* **Why it is useful:** It updates your dot sizes **instantly** in the viewport without needing to wait for a new AI scan.

---

### View through camera Button (`moge_splat.view_camera`)
* **What it does:** Snaps the active 3D viewport directly to the generated `MoGe_Camera`, switches the viewport shading to **Material Preview**, and activates camera framing with a 100% black passepartout mask.

---

## 7. 2.5D Compositor Relighter

Found inside collapsible box **4. 2.5D relight (compositor)**.

### Setup relighter Button (`moge_splat.setup_relight`)
* **What it does:** Automatically builds a complete 2.5D diffuse relighting node tree in Blender’s Compositor using the camera plate and the AI-generated 3D surface normal map.
* **How to use it:**
  1. Click **Setup relighter**.
  2. Switch to Blender’s **Compositing** workspace (or open the Node Editor).
  3. Look for the node labeled **Light Direction** (the sphere gizmo).
  4. Click and drag the sphere normal gizmo to dynamically move a simulated directional light across the 2D photo!
  5. Tweak **Key Light Color**, **Light Intensity**, and **Ambient Fill** nodes to adjust mood and fill brightness.

---

## 8. Grid Levelling (Aligning Floor to Z=0)

Found inside box **5. Grid level**.

When scanning from a handheld photo, the camera is often tilted. This means the floor in Blender ends up slanted at an awkward angle. The Levelling tools solve this by parenting the scan to a helper empty (`MoGe_Level`) and rotating it so the floor rests flat at $Z = 0.0$.

```
RAW SCAN (Slanted floor)             AFTER LEVELLING (Floor at Z=0)
       \                                       |
        \   [Slanted Room]                     |   [Leveled Room]
_________\_________________             _______|__________________ (Z = 0 Ground)
```

### Level floor (auto) (`moge_splat.level_auto`)
* **What it does:** Sends the cached scan maps to a RANSAC plane-fitting algorithm. It detects the primary floor plane (ignoring ceilings and walls) and automatically levels the scene.
* **Best for:** Clear indoor floors, streets, sidewalks, and flat ground.

---

### Add markers (`moge_splat.level_markers_add`)
* **What it does:** Spawns three helper empties (`MoGe_Floor_A`, `MoGe_Floor_B`, `MoGe_Floor_C`) in front of the camera.
* **When to use:** When the automatic leveler is confused (e.g. cluttered rooms with beds and rugs).

---

### Level to markers (`moge_splat.level_markers_apply`)
* **What it does:** Calculates the geometric plane defined by the three markers and rotates the entire scene so that plane becomes flat at $Z = 0$.
* **How to use:**
  1. Click **Add markers**.
  2. In the 3D viewport, grab and move markers A, B, and C so they sit on three distinct spots on the floor (forming a triangle).
  3. Click **Level to markers**.

---

### Remove levelling (`moge_splat.level_remove`)
* **What it does:** Deletes the `MoGe_Level` helper empty and un-parents the camera and splats, restoring the scene back to its raw camera-relative coordinates.
* **Safety feature:** It never destroys or degrades your raw geometric point data.

---

## 9. Diagnostic Metadata Viewer

Found inside collapsible box **6. Scan metadata**.

Provides an instant technical audit of the last scan:
* **Image:** Filename, native dimensions vs inference dimensions.
* **Model:** Checkpoint version (`v3/vitl` or `v3/vitg`) and TTA status.
* **FOV:** Shows horizontal x vertical degrees, plus the source (`exif`, `manual`, or `model`).
* **Depth:** Physical metric range in meters (e.g., `0.42m .. 18.50m`).
* **Splats:** Point count and texture color source (e.g., `1,142,850 | native 4032x3024`).
* **Radius:** Details whether uniform or adaptive sizing was applied.
* **Level:** Displays floor tilt compensation angle (e.g., `tilt was 8.4deg | floor at z=0`).

---

## 10. Troubleshooting Visual Artifacts

### 1. "The background has giant stretched curtains connecting it to the foreground"
* **Cause:** *Surface Mode* is set to **Seamless**, which preserves every continuous triangle/point regardless of depth distance.
* **Fix:** Change *Surface Mode* to **Split Islands**. This cuts points across sharp depth edges.

---

### 2. "The sky turned into a solid geometric wall"
* **Cause:** The sky in the photo was recognized as far geometry.
* **Fix:** Set *Surface Mode* to **Masked** or **Split Islands** with **Mask sky/void** enabled.

---

### 3. "The scene looks like a screen-door mesh with holes between points"
* **Cause:** Either *Uniform radius* is set to a fixed small number, or *Adaptive scale* is too low.
* **Fix:**
  1. Ensure **Uniform m** is set to `0.0` (activates adaptive scaling).
  2. Increase **Adaptive scale** from `1.0` to `1.3` or `1.5`.
  3. Click **Apply radius**.

---

### 4. "Points look like huge blurry blobs up close"
* **Cause:** *Adaptive scale* is set too high, or a fixed uniform radius is too large.
* **Fix:** Lower **Adaptive scale** to `0.7` or `0.8` and click **Apply radius**.

---

### 5. "Blender 3D Viewport is lagging or dropping frames"
* **Cause:** Point budget is too high for your current viewport settings.
* **Fix:** Set **Point budget** to `800,000` or `1,000,000`, and click **Scan -> Splats** again.

---

### 6. "The Relighter compositing output is completely black"
* **Cause:** An older blend file was loaded, or nodes need an update.
* **Fix:** Re-click **Setup relighter** in Box 4. MoGe Splat Studio will auto-detect Blender 5.2 unified color sockets and bind the correct Image interface.
