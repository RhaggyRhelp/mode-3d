"""Edge-preserving normal-guided depth filtering for MoGe v3.

Provides two complementary methods to eliminate monocular Z-jitter and undulations
while strictly preserving sharp structural edges and crease corners:

1. GuidedFilter: Fast O(1) box-convolution guided filter (He et al.).
   Uses surface normals (or RGB) as guidance over inverse-depth (disparity)
   or metric depth. Runs on GPU (PyTorch) in ~2-5ms or CPU (NumPy).

2. TangentPlaneBilateralFilter: Perspective-exact normal-weighted bilateral filter.
   Each neighbor on a plane projects its tangent plane:
     Z_p^(q) = (n_q . x_q) / (n_q . r_p)
   Eliminates perspective slope distortion on slanted walls/floors.
"""
from __future__ import annotations

import math
from typing import Optional, Union, Tuple
import numpy as np


# ---------------------------------------------------------------------------
# NumPy Box Filter / Integral Image
# ---------------------------------------------------------------------------

def _box_filter_2d_np(img: np.ndarray, r: int) -> np.ndarray:
    """Box filter (mean in (2r+1)x(2r+1) window) for 2D or 3D NumPy array."""
    if r <= 0:
        return img.copy()
    k_size = 2 * r + 1
    # Use uniform filter if scipy available, else pad and cumulative sum
    try:
        from scipy.ndimage import uniform_filter
        if img.ndim == 2:
            return uniform_filter(img, size=k_size, mode='reflect')
        elif img.ndim == 3:
            out = np.empty_like(img)
            for c in range(img.shape[2]):
                out[..., c] = uniform_filter(img[..., c], size=k_size, mode='reflect')
            return out
    except ImportError:
        pass

    # Fast integral image fallback
    H, W = img.shape[:2]
    pad_img = np.pad(img, ((r + 1, r), (r + 1, r)) if img.ndim == 2 else ((r + 1, r), (r + 1, r), (0, 0)),
                     mode='edge')
    if img.ndim == 2:
        sat = np.cumsum(np.cumsum(pad_img, axis=0), axis=1)
        res = (sat[k_size:, k_size:] - sat[:-k_size, k_size:] -
               sat[k_size:, :-k_size] + sat[:-k_size, :-k_size])
        return res / (k_size * k_size)
    else:
        C = img.shape[2]
        out = np.empty_like(img)
        for c in range(C):
            sat = np.cumsum(np.cumsum(pad_img[..., c], axis=0), axis=1)
            res = (sat[k_size:, k_size:] - sat[:-k_size, k_size:] -
                   sat[k_size:, :-k_size] + sat[:-k_size, :-k_size])
            out[..., c] = res / (k_size * k_size)
        return out


# ---------------------------------------------------------------------------
# PyTorch GPU Guided Filter (Fastest)
# ---------------------------------------------------------------------------

def _guided_filter_torch(depth: "torch.Tensor", guide: "torch.Tensor",
                         r: int = 5, eps: float = 1e-3) -> "torch.Tensor":
    """GPU guided filter using PyTorch avg_pool2d.
    
    depth: (1, 1, H, W) float32
    guide: (1, C, H, W) float32 (e.g. C=3 for normal map)
    """
    import torch
    import torch.nn.functional as F

    k_size = 2 * r + 1
    pad = r

    def box(x):
        return F.avg_pool2d(x, kernel_size=k_size, stride=1, padding=pad, count_include_pad=False)

    N_channels = guide.shape[1]
    mean_I = box(guide)                               # (1, C, H, W)
    mean_p = box(depth)                               # (1, 1, H, W)
    mean_Ip = box(guide * depth)                      # (1, C, H, W)
    cov_Ip = mean_Ip - mean_I * mean_p                # (1, C, H, W)

    if N_channels == 1:
        mean_II = box(guide * guide)
        var_I = mean_II - mean_I * mean_I
        a = cov_Ip / (var_I + eps)
        b = mean_p - a * mean_I
        q = box(a) * guide + box(b)
        return q

    elif N_channels == 3:
        # Multichannel 3x3 covariance per pixel
        I_x, I_y, I_z = guide[:, 0:1], guide[:, 1:2], guide[:, 2:3]
        var_I_xx = box(I_x * I_x) - mean_I[:, 0:1] * mean_I[:, 0:1] + eps
        var_I_yy = box(I_y * I_y) - mean_I[:, 1:2] * mean_I[:, 1:2] + eps
        var_I_zz = box(I_z * I_z) - mean_I[:, 2:3] * mean_I[:, 2:3] + eps
        var_I_xy = box(I_x * I_y) - mean_I[:, 0:1] * mean_I[:, 1:2]
        var_I_xz = box(I_x * I_z) - mean_I[:, 0:1] * mean_I[:, 2:3]
        var_I_yz = box(I_y * I_z) - mean_I[:, 1:2] * mean_I[:, 2:3]

        cov_x = cov_Ip[:, 0:1]
        cov_y = cov_Ip[:, 1:2]
        cov_z = cov_Ip[:, 2:3]

        # Invert 3x3 symmetric matrix per pixel analytically
        det = (var_I_xx * (var_I_yy * var_I_zz - var_I_yz * var_I_yz) -
               var_I_xy * (var_I_xy * var_I_zz - var_I_xz * var_I_yz) +
               var_I_xz * (var_I_xy * var_I_yz - var_I_xz * var_I_yy))
        det = torch.clamp(det, min=1e-8)

        inv_xx = (var_I_yy * var_I_zz - var_I_yz * var_I_yz) / det
        inv_yy = (var_I_xx * var_I_zz - var_I_xz * var_I_xz) / det
        inv_zz = (var_I_xx * var_I_yy - var_I_xy * var_I_xy) / det
        inv_xy = (var_I_xz * var_I_yz - var_I_xy * var_I_zz) / det
        inv_xz = (var_I_xy * var_I_yz - var_I_xz * var_I_yy) / det
        inv_yz = (var_I_xy * var_I_xz - var_I_yz * var_I_xx) / det

        a_x = inv_xx * cov_x + inv_xy * cov_y + inv_xz * cov_z
        a_y = inv_xy * cov_x + inv_yy * cov_y + inv_yz * cov_z
        a_z = inv_xz * cov_x + inv_yz * cov_y + inv_zz * cov_z

        b = mean_p - (a_x * mean_I[:, 0:1] + a_y * mean_I[:, 1:2] + a_z * mean_I[:, 2:3])
        q = (box(a_x) * I_x + box(a_y) * I_y + box(a_z) * I_z) + box(b)
        return q

    raise ValueError(f"Unsupported guide channels: {N_channels}")


# ---------------------------------------------------------------------------
# NumPy Guided Filter
# ---------------------------------------------------------------------------

def _guided_filter_np(depth: np.ndarray, guide: np.ndarray,
                      r: int = 5, eps: float = 1e-3) -> np.ndarray:
    """NumPy implementation of guided filter."""
    k_size = 2 * r + 1
    if guide.ndim == 2:
        guide = guide[..., np.newaxis]
    C = guide.shape[2]

    mean_I = _box_filter_2d_np(guide, r)
    mean_p = _box_filter_2d_np(depth, r)

    if C == 1:
        mean_Ip = _box_filter_2d_np(guide[..., 0] * depth, r)
        cov_Ip = mean_Ip - mean_I[..., 0] * mean_p
        mean_II = _box_filter_2d_np(guide[..., 0] ** 2, r)
        var_I = mean_II - mean_I[..., 0] ** 2
        a = cov_Ip / (var_I + eps)
        b = mean_p - a * mean_I[..., 0]
        q = _box_filter_2d_np(a, r) * guide[..., 0] + _box_filter_2d_np(b, r)
        return q

    elif C == 3:
        I_x, I_y, I_z = guide[..., 0], guide[..., 1], guide[..., 2]
        mean_Ix, mean_Iy, mean_Iz = mean_I[..., 0], mean_I[..., 1], mean_I[..., 2]

        cov_x = _box_filter_2d_np(I_x * depth, r) - mean_Ix * mean_p
        cov_y = _box_filter_2d_np(I_y * depth, r) - mean_Iy * mean_p
        cov_z = _box_filter_2d_np(I_z * depth, r) - mean_Iz * mean_p

        var_xx = _box_filter_2d_np(I_x * I_x, r) - mean_Ix * mean_Ix + eps
        var_yy = _box_filter_2d_np(I_y * I_y, r) - mean_Iy * mean_Iy + eps
        var_zz = _box_filter_2d_np(I_z * I_z, r) - mean_Iz * mean_Iz + eps
        var_xy = _box_filter_2d_np(I_x * I_y, r) - mean_Ix * mean_Iy
        var_xz = _box_filter_2d_np(I_x * I_z, r) - mean_Ix * mean_Iz
        var_yz = _box_filter_2d_np(I_y * I_z, r) - mean_Iy * mean_Iz

        det = (var_xx * (var_yy * var_zz - var_yz * var_yz) -
               var_xy * (var_xy * var_zz - var_xz * var_yz) +
               var_xz * (var_xy * var_yz - var_xz * var_yy))
        det = np.maximum(det, 1e-8)

        inv_xx = (var_yy * var_zz - var_yz * var_yz) / det
        inv_yy = (var_xx * var_zz - var_xz * var_xz) / det
        inv_zz = (var_xx * var_yy - var_xy * var_xy) / det
        inv_xy = (var_xz * var_yz - var_xy * var_zz) / det
        inv_xz = (var_xy * var_yz - var_xz * var_yy) / det
        inv_yz = (var_xy * var_xz - var_yz * var_xx) / det

        a_x = inv_xx * cov_x + inv_xy * cov_y + inv_xz * cov_z
        a_y = inv_xy * cov_x + inv_yy * cov_y + inv_yz * cov_z
        a_z = inv_xz * cov_x + inv_yz * cov_y + inv_zz * cov_z

        b = mean_p - (a_x * mean_Ix + a_y * mean_Iy + a_z * mean_Iz)
        q = (_box_filter_2d_np(a_x, r) * I_x +
             _box_filter_2d_np(a_y, r) * I_y +
             _box_filter_2d_np(a_z, r) * I_z +
             _box_filter_2d_np(b, r))
        return q

    raise ValueError(f"Unsupported guide channels: {C}")


# ---------------------------------------------------------------------------
# Tangent-Plane Perspective Bilateral Filter
# ---------------------------------------------------------------------------

def filter_depth_tangent_plane(points: np.ndarray, normals: np.ndarray,
                               intrinsics: np.ndarray, mask: Optional[np.ndarray] = None,
                               radius: int = 4, normal_power: float = 6.0,
                               sigma_spatial: float = 2.5) -> np.ndarray:
    """Perspective-exact tangent-plane bilateral filter.
    
    For each pixel p with viewing ray r_p = K^-1 [u, v, 1]^T, each neighboring
    pixel q with 3D point x_q and normal n_q defines a tangent plane:
        Z_p^(q) = (n_q . x_q) / (n_q . r_p)
    
    Weights are:
        w_spatial = exp(-||p - q||^2 / (2 * sigma_s^2))
        w_normal  = max(0, n_p . n_q)^normal_power
    
    This ensures that slanted perspective planes (floors, walls) are filtered
    without any perspective slope distortion.
    """
    H, W = points.shape[:2]
    fx = float(intrinsics[0, 0] * W if intrinsics[0, 0] <= 1.0 else intrinsics[0, 0])
    fy = float(intrinsics[1, 1] * H if intrinsics[1, 1] <= 1.0 else intrinsics[1, 1])
    cx = float(intrinsics[0, 2] * W if intrinsics[0, 2] <= 1.0 else intrinsics[0, 2])
    cy = float(intrinsics[1, 2] * H if intrinsics[1, 2] <= 1.0 else intrinsics[1, 2])

    us, vs = np.meshgrid(np.arange(W, dtype=np.float32), np.arange(H, dtype=np.float32))
    # Normalized viewing rays
    rx = (us - cx) / fx
    ry = (vs - cy) / fy
    rz = np.ones_like(rx)
    ray = np.stack([rx, ry, rz], axis=-1)  # (H, W, 3)

    if mask is None:
        mask = np.isfinite(points[..., 2]) & (points[..., 2] > 0.05)

    n_dots_x = np.sum(normals * points, axis=-1)  # d = n . x

    out_depth = np.zeros((H, W), dtype=np.float32)
    weight_sum = np.zeros((H, W), dtype=np.float32)

    # Shift offsets
    for dy in range(-radius, radius + 1):
        for dx in range(-radius, radius + 1):
            if dx == 0 and dy == 0:
                dist_sq = 0.0
                w_s = 1.0
            else:
                dist_sq = float(dx * dx + dy * dy)
                if dist_sq > radius * radius:
                    continue
                w_s = math.exp(-dist_sq / (2.0 * sigma_spatial * sigma_spatial))

            # Slices for neighbor q = (y+dy, x+dx) mapped to p = (y, x)
            y_src = slice(max(0, dy), min(H, H + dy))
            x_src = slice(max(0, dx), min(W, W + dx))
            y_dst = slice(max(0, -dy), min(H, H - dy))
            x_dst = slice(max(0, -dx), min(W, W - dx))

            # Neighbor normal, d, and mask
            n_q = normals[y_src, x_src]
            d_q = n_dots_x[y_src, x_src]
            m_q = mask[y_src, x_src]

            # Current pixel normal and ray
            n_p = normals[y_dst, x_dst]
            r_p = ray[y_dst, x_dst]
            m_p = mask[y_dst, x_dst]

            # Normal similarity
            n_dot = np.sum(n_p * n_q, axis=-1)
            valid_pair = m_q & m_p & (n_dot > 0.1)

            # Denominator: n_q . r_p
            n_q_dot_r_p = np.sum(n_q * r_p, axis=-1)
            valid_geom = np.abs(n_q_dot_r_p) > 1e-4

            valid = valid_pair & valid_geom
            w_n = np.zeros_like(n_dot)
            w_n[valid] = np.power(np.maximum(0.0, n_dot[valid]), normal_power)

            w_total = w_s * w_n

            # Predicted Z
            z_pred = np.zeros_like(d_q)
            z_pred[valid] = d_q[valid] / n_q_dot_r_p[valid]

            # Reject non-physical predictions (>1.5x or <0.6x of current depth)
            curr_z = points[y_dst, x_dst, 2]
            plausible = valid & (z_pred > curr_z * 0.6) & (z_pred < curr_z * 1.5)

            out_depth[y_dst, x_dst] += np.where(plausible, z_pred * w_total, 0.0)
            weight_sum[y_dst, x_dst] += np.where(plausible, w_total, 0.0)

    # Normalize
    good = weight_sum > 1e-5
    result = points[..., 2].copy()
    result[good] = out_depth[good] / weight_sum[good]
    return result


# ---------------------------------------------------------------------------
# High-Level Unified API
# ---------------------------------------------------------------------------

def filter_depth_map(depth: np.ndarray,
                     normal: np.ndarray,
                     mask: Optional[np.ndarray] = None,
                     intrinsics: Optional[np.ndarray] = None,
                     method: str = "guided",
                     radius: int = 5,
                     eps: float = 1e-3,
                     use_gpu: bool = True) -> np.ndarray:
    """Filter depth map to eliminate undulations while keeping crisp structural edges.

    Args:
        depth: (H, W) metric depth array.
        normal: (H, W, 3) surface normals (e.g. from MoGe v3).
        mask: (H, W) bool valid mask.
        intrinsics: (3, 3) camera intrinsics matrix.
        method: "guided" (multichannel guided filter on inverse depth) or
                "tangent_plane" (perspective tangent bilateral filter).
        radius: filter radius in pixels.
        eps: regularization parameter for guided filter.
        use_gpu: whether to use PyTorch CUDA acceleration if available.

    Returns:
        (H, W) cleaned depth array.
    """
    H, W = depth.shape[:2]
    finite = np.isfinite(depth) & (depth > 0.01)
    if mask is not None:
        finite = finite & mask

    if method == "tangent_plane":
        if intrinsics is None:
            raise ValueError("tangent_plane method requires camera intrinsics")
        # Build 3D points from depth
        fx = float(intrinsics[0, 0] * W if intrinsics[0, 0] <= 1.0 else intrinsics[0, 0])
        fy = float(intrinsics[1, 1] * H if intrinsics[1, 1] <= 1.0 else intrinsics[1, 1])
        cx = float(intrinsics[0, 2] * W if intrinsics[0, 2] <= 1.0 else intrinsics[0, 2])
        cy = float(intrinsics[1, 2] * H if intrinsics[1, 2] <= 1.0 else intrinsics[1, 2])
        us, vs = np.meshgrid(np.arange(W), np.arange(H))
        X = (us - cx) * depth / fx
        Y = (vs - cy) * depth / fy
        points = np.stack([X, Y, depth], axis=-1)
        return filter_depth_tangent_plane(points, normal, intrinsics, mask=finite, radius=radius)

    # Default: Guided Filter on inverse depth (disparity = 1/Z)
    # Inverse depth is strictly affine on planes, ensuring linear behavior.
    disp = np.zeros_like(depth)
    disp[finite] = 1.0 / np.maximum(depth[finite], 1e-4)

    # Normalize normal vectors
    n_norm = np.linalg.norm(normal, axis=-1, keepdims=True)
    normal_unit = np.where(n_norm > 1e-6, normal / np.maximum(n_norm, 1e-6), 0.0)

    filtered_disp = None
    if use_gpu:
        try:
            import torch
            if torch.cuda.is_available():
                t_disp = torch.from_numpy(disp[None, None, ...]).float().cuda()
                t_norm = torch.from_numpy(normal_unit.transpose(2, 0, 1)[None, ...]).float().cuda()
                t_out = _guided_filter_torch(t_disp, t_norm, r=radius, eps=eps)
                filtered_disp = t_out.squeeze().cpu().numpy()
        except Exception:
            filtered_disp = None

    if filtered_disp is None:
        filtered_disp = _guided_filter_np(disp, normal_unit, r=radius, eps=eps)

    # Invert back to metric depth
    clean_depth = depth.copy()
    valid_disp = (filtered_disp > 1e-5) & finite
    clean_depth[valid_disp] = 1.0 / filtered_disp[valid_disp]
    return clean_depth
