# Benched Experiment: 360 Panoramic Room Reconstruction

**Date Benched:** September 3, 2026  
**Status:** Benched / Shelved for future reference  
**Origin:** Experimental feature in MoGe Splat Studio  

---

## 1. Concept & Objective
The goal of this experiment was to take a single 2:1 equirectangular 360 photo and automatically generate a complete, aligned 3D room point cloud in Blender without manual alignment, photogrammetry tracking, or multi-view ICP.

---

## 2. Benched Artifacts in this Directory
1. `shared_pano.py`:
   - Gnomonic tangent extraction (`extract_face` with cv2/bilinear).
   - Boundary ray column matching (`boundary_columns`).
   - Scalar & Affine loop-closed scale solvers (`solve_scales`, `solve_affine`).
   - Exclusive angular display wedges (`side_wedge_mask`, `pole_cap_mask`).
2. `test_pano.py`:
   - Full test suite verifying right-handed frames, scale recovery, flat-wall bas-relief stability, and cubemap geometry.
3. `daemon_pano_endpoint.py`:
   - The FastAPI `/pano` endpoint handling multipart image upload, multi-face inference, reprojection, and uncompressed `.npz` streaming.
4. `blender_pano_addon_snippet.py`:
   - The Blender camera rig builder (`_build_pano_rig`), operator (`MOGE_OT_scan_pano`), and UI box.

---

## 3. Key Findings & Performance Metrics
* **Scan Latency:** **2.8 seconds** for 4 walls (691,200 points), **2.9 seconds** for 6-face full room (1,076,538 points) on RTX 4070 Ti Super.
* **Seam Residual Error:** **3.0%** across room corners.
* **Affine Alignment:** Successfully prevented degenerate bas-relief collapse via Tikhonov delta regularization.

---

## 4. Why It Was Benched (The Mathematical Ceiling)
1. **Pinhole Perspective vs. Spherical Reality:** Monocular models trained on flat images have no spherical awareness. Slicing with flat planar frustums and cutting with hard boundary wedges creates stair-step tears whenever a protruding 3D object (such as an air conditioner) crosses a seam line.
2. **Camera Center Sensitivity:** Cubemaps assume seams match room corners (45, 135, 225, 315 deg). If the 360 camera is not placed dead-center in the room, the seams cut through flat walls and furniture rather than room corners.
