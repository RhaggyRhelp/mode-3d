"""2.5D structured mesh builder for MoGe v3 depth and normal maps.

Converts filtered (or raw) depth maps and normals into 3D meshes while respecting
grid topology, cutting depth curtains/discontinuities, and exporting to OBJ/PLY.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional, Tuple, Dict, Any
import numpy as np


def build_mesh_from_depth(
    depth: np.ndarray,
    intrinsics: np.ndarray,
    normal: Optional[np.ndarray] = None,
    image: Optional[np.ndarray] = None,
    mask: Optional[np.ndarray] = None,
    stride: int = 1,
    max_depth_ratio: float = 0.06,
    coordinate_system: str = "blender",
    snap_plane: Optional[Tuple[np.ndarray, float, np.ndarray]] = None,
) -> Dict[str, np.ndarray]:
    """Construct structured 2.5D triangle mesh from depth map.

    Args:
        depth: (H, W) metric depth array.
        intrinsics: (3, 3) normalized or absolute pinhole camera intrinsics.
        normal: (H, W, 3) surface normals in camera space.
        image: (H, W, 3) uint8 or float RGB image.
        mask: (H, W) bool validity mask (where False, vertices/faces are omitted).
        stride: downsample factor (1 = full native resolution).
        max_depth_ratio: maximum relative depth change between neighboring vertices
                         (|Z1 - Z2| / min(Z1, Z2)). Rejects edge curtains.
        coordinate_system: "blender" (X right, Y depth, Z up) or "opencv" (X right, Y down, Z forward).
        snap_plane: Optional tuple of (plane_normal, plane_d, plane_inlier_mask) to snap
                    detected RANSAC planes to exact mathematical coplanarity.

    Returns:
        dict with keys:
            'vertices': (V, 3) float32
            'faces': (F, 3) int32
            'uvs': (V, 2) float32
            'normals': (V, 3) float32 (if normal provided)
            'colors': (V, 3) float32 (if image provided, range 0..1)
    """
    H, W = depth.shape[:2]

    # Resolve intrinsics
    fx = float(intrinsics[0, 0] * W if intrinsics[0, 0] <= 1.0 else intrinsics[0, 0])
    fy = float(intrinsics[1, 1] * H if intrinsics[1, 1] <= 1.0 else intrinsics[1, 1])
    cx = float(intrinsics[0, 2] * W if intrinsics[0, 2] <= 1.0 else intrinsics[0, 2])
    cy = float(intrinsics[1, 2] * H if intrinsics[1, 2] <= 1.0 else intrinsics[1, 2])

    # Downsample if stride > 1
    if stride > 1:
        depth_sub = depth[::stride, ::stride]
        if mask is not None:
            mask_sub = mask[::stride, ::stride]
        else:
            mask_sub = None
        if normal is not None:
            normal_sub = normal[::stride, ::stride]
        else:
            normal_sub = None
        if image is not None:
            image_sub = image[::stride, ::stride]
        else:
            image_sub = None
        Hs, Ws = depth_sub.shape[:2]
        ys_idx, xs_idx = np.meshgrid(np.arange(0, H, stride)[:Ws], np.arange(0, W, stride)[:Hs])
        # Re-index meshgrid correctly
        xs_px, ys_px = np.meshgrid(np.arange(0, W, stride), np.arange(0, H, stride))
    else:
        depth_sub = depth
        mask_sub = mask
        normal_sub = normal
        image_sub = image
        Hs, Ws = H, W
        xs_px, ys_px = np.meshgrid(np.arange(W, dtype=np.float32), np.arange(H, dtype=np.float32))

    # Compute 3D points in OpenCV camera frame: X = (u - cx)*Z/fx, Y = (v - cy)*Z/fy, Z = depth
    X = (xs_px - cx) * depth_sub / fx
    Y = (ys_px - cy) * depth_sub / fy
    Z = depth_sub.astype(np.float32)

    # Optional: snap points to detected mathematical plane
    if snap_plane is not None:
        p_norm, p_d, p_inliers = snap_plane
        if stride > 1 and p_inliers.shape != depth_sub.shape:
            p_inliers = p_inliers[::stride, ::stride]
        # dist = n . x + d
        P_cv = np.stack([X, Y, Z], axis=-1)
        dist = np.sum(P_cv * p_norm, axis=-1) + p_d
        in_p = p_inliers & np.isfinite(dist)
        X[in_p] -= (dist[in_p] * p_norm[0])
        Y[in_p] -= (dist[in_p] * p_norm[1])
        Z[in_p] -= (dist[in_p] * p_norm[2])

    # Convert coordinates
    if coordinate_system.lower() == "blender":
        # Blender: X_b = X_cv, Y_b = Z_cv, Z_b = -Y_cv
        pts_3d = np.stack([X, Z, -Y], axis=-1)
        if normal_sub is not None:
            # Normals rotate identically
            norms_3d = np.stack([normal_sub[..., 0], normal_sub[..., 2], -normal_sub[..., 1]], axis=-1)
        else:
            norms_3d = None
    else:
        pts_3d = np.stack([X, Y, Z], axis=-1)
        norms_3d = normal_sub

    # Validity mask
    valid = np.isfinite(Z) & (Z > 0.05)
    if mask_sub is not None:
        valid = valid & mask_sub

    # Grid indices: 2D array of vertex indices (-1 if invalid)
    vert_grid = np.full((Hs, Ws), -1, dtype=np.int32)
    valid_idx = np.where(valid)
    num_verts = len(valid_idx[0])
    vert_grid[valid_idx] = np.arange(num_verts, dtype=np.int32)

    # Extract valid vertex attributes
    vertices = pts_3d[valid_idx].astype(np.float32)

    # UVs (normalized 0..1, V inverted for OpenGL/Blender convention)
    u_coords = xs_px[valid_idx] / float(W - 1)
    v_coords = 1.0 - (ys_px[valid_idx] / float(H - 1))
    uvs = np.stack([u_coords, v_coords], axis=-1).astype(np.float32)

    out_normals = norms_3d[valid_idx].astype(np.float32) if norms_3d is not None else None

    if image_sub is not None:
        img_f = image_sub[valid_idx].astype(np.float32)
        if img_f.max() > 1.0:
            img_f /= 255.0
        out_colors = img_f
    else:
        out_colors = None

    # Construct faces
    # For each cell (r, c), vertices are:
    # v00: (r, c)       v01: (r, c+1)
    # v10: (r+1, c)     v11: (r+1, c+1)
    v00 = vert_grid[:-1, :-1].ravel()
    v01 = vert_grid[:-1, 1:].ravel()
    v10 = vert_grid[1:, :-1].ravel()
    v11 = vert_grid[1:, 1:].ravel()

    z00 = Z[:-1, :-1].ravel()
    z01 = Z[:-1, 1:].ravel()
    z10 = Z[1:, :-1].ravel()
    z11 = Z[1:, 1:].ravel()

    # Triangle 1: (v00, v10, v01)
    valid_t1 = (v00 >= 0) & (v10 >= 0) & (v01 >= 0)
    # Depth continuity check
    min_z1 = np.minimum(np.minimum(z00, z10), z01)
    max_z1 = np.maximum(np.maximum(z00, z10), z01)
    cont_t1 = ((max_z1 - min_z1) / np.maximum(min_z1, 1e-4)) < max_depth_ratio
    keep_t1 = valid_t1 & cont_t1

    # Triangle 2: (v01, v10, v11)
    valid_t2 = (v01 >= 0) & (v10 >= 0) & (v11 >= 0)
    min_z2 = np.minimum(np.minimum(z01, z10), z11)
    max_z2 = np.maximum(np.maximum(z01, z10), z11)
    cont_t2 = ((max_z2 - min_z2) / np.maximum(min_z2, 1e-4)) < max_depth_ratio
    keep_t2 = valid_t2 & cont_t2

    t1_faces = np.stack([v00[keep_t1], v10[keep_t1], v01[keep_t1]], axis=-1)
    t2_faces = np.stack([v01[keep_t2], v10[keep_t2], v11[keep_t2]], axis=-1)

    faces = np.vstack([t1_faces, t2_faces]).astype(np.int32)

    # Clean up isolated unused vertices
    used_verts = np.unique(faces)
    remap = np.full(num_verts, -1, dtype=np.int32)
    remap[used_verts] = np.arange(len(used_verts), dtype=np.int32)

    faces = remap[faces]
    vertices = vertices[used_verts]
    uvs = uvs[used_verts]
    if out_normals is not None:
        out_normals = out_normals[used_verts]
    if out_colors is not None:
        out_colors = out_colors[used_verts]

    return {
        "vertices": vertices,
        "faces": faces,
        "uvs": uvs,
        "normals": out_normals,
        "colors": out_colors,
    }


def export_obj(
    filepath: Union[str, Path],
    vertices: np.ndarray,
    faces: np.ndarray,
    uvs: Optional[np.ndarray] = None,
    normals: Optional[np.ndarray] = None,
    colors: Optional[np.ndarray] = None,
) -> None:
    """Export triangle mesh to Wavefront OBJ format with optional vertex colors and UVs."""
    filepath = Path(filepath)
    filepath.parent.mkdir(parents=True, exist_ok=True)

    has_uv = uvs is not None and len(uvs) == len(vertices)
    has_norm = normals is not None and len(normals) == len(vertices)
    has_col = colors is not None and len(colors) == len(vertices)

    with open(filepath, "w", encoding="utf-8") as f:
        f.write("# MoGe Splat Studio 2.5D Mesh Export\n")
        # Vertices (+ colors if present: v X Y Z R G B)
        if has_col:
            for v, c in zip(vertices, colors):
                f.write(f"v {v[0]:.5f} {v[1]:.5f} {v[2]:.5f} {c[0]:.4f} {c[1]:.4f} {c[2]:.4f}\n")
        else:
            for v in vertices:
                f.write(f"v {v[0]:.5f} {v[1]:.5f} {v[2]:.5f}\n")

        # Texture coordinates
        if has_uv:
            for uv in uvs:
                f.write(f"vt {uv[0]:.5f} {uv[1]:.5f}\n")

        # Normals
        if has_norm:
            for n in normals:
                f.write(f"vn {n[0]:.4f} {n[1]:.4f} {n[2]:.4f}\n")

        # Faces (1-indexed in OBJ)
        # format: f v/vt/vn
        faces_1idx = faces + 1
        if has_uv and has_norm:
            for face in faces_1idx:
                f.write(f"f {face[0]}/{face[0]}/{face[0]} {face[1]}/{face[1]}/{face[1]} {face[2]}/{face[2]}/{face[2]}\n")
        elif has_uv:
            for face in faces_1idx:
                f.write(f"f {face[0]}/{face[0]} {face[1]}/{face[1]} {face[2]}/{face[2]}\n")
        elif has_norm:
            for face in faces_1idx:
                f.write(f"f {face[0]}//{face[0]} {face[1]}//{face[1]} {face[2]}//{face[2]}\n")
        else:
            for face in faces_1idx:
                f.write(f"f {face[0]} {face[1]} {face[2]}\n")


def export_ply(
    filepath: Union[str, Path],
    vertices: np.ndarray,
    faces: np.ndarray,
    colors: Optional[np.ndarray] = None,
    normals: Optional[np.ndarray] = None,
) -> None:
    """Export triangle mesh to binary little-endian PLY format."""
    filepath = Path(filepath)
    filepath.parent.mkdir(parents=True, exist_ok=True)

    V = len(vertices)
    F = len(faces)
    has_col = colors is not None and len(colors) == V
    has_norm = normals is not None and len(normals) == V

    header = [
        "ply",
        "format binary_little_endian 1.0",
        f"element vertex {V}",
        "property float x",
        "property float y",
        "property float z",
    ]
    if has_norm:
        header.extend([
            "property float nx",
            "property float ny",
            "property float nz",
        ])
    if has_col:
        header.extend([
            "property uchar red",
            "property uchar green",
            "property uchar blue",
        ])
    header.extend([
        f"element face {F}",
        "property list uchar int vertex_indices",
        "end_header\n"
    ])

    with open(filepath, "wb") as f:
        f.write("\n".join(header).encode("ascii"))
        # Pack vertices
        v_dtype = [("x", "<f4"), ("y", "<f4"), ("z", "<f4")]
        if has_norm:
            v_dtype.extend([("nx", "<f4"), ("ny", "<f4"), ("nz", "<f4")])
        if has_col:
            v_dtype.extend([("red", "u1"), ("green", "u1"), ("blue", "u1")])

        v_data = np.empty(V, dtype=v_dtype)
        v_data["x"] = vertices[:, 0]
        v_data["y"] = vertices[:, 1]
        v_data["z"] = vertices[:, 2]
        if has_norm:
            v_data["nx"] = normals[:, 0]
            v_data["ny"] = normals[:, 1]
            v_data["nz"] = normals[:, 2]
        if has_col:
            c_u8 = (np.clip(colors, 0.0, 1.0) * 255.0).astype(np.uint8)
            v_data["red"] = c_u8[:, 0]
            v_data["green"] = c_u8[:, 1]
            v_data["blue"] = c_u8[:, 2]
        f.write(v_data.tobytes())

        # Pack faces: (uchar count = 3, int32 v0, int32 v1, int32 v2)
        f_dtype = [("count", "u1"), ("v0", "<i4"), ("v1", "<i4"), ("v2", "<i4")]
        f_data = np.empty(F, dtype=f_dtype)
        f_data["count"] = 3
        f_data["v0"] = faces[:, 0]
        f_data["v1"] = faces[:, 1]
        f_data["v2"] = faces[:, 2]
        f_data.tofile(f)
