"""Crop-zoom alignment math. Numpy only.

A crop is NOT a new viewpoint: same camera center, narrower FOV. With the
parent's normalized intrinsics K and the crop rect in full-res pixels, the
crop-center ray is d = ((ccx-0.5)/K00, (ccy-0.5)/K11, 1). MoGe infers the crop
as if centered, so crop points map to the parent frame by R: (0,0,1) -> d.
Focal for the crop inference (drives MoGe's own projection): from fx scaled
to crop-infer pixels. All formulas resolution-independent via normalized K.
"""
from __future__ import annotations

import math
import numpy as np


def crop_fov_x(K: np.ndarray, orig_w: float, crop_nat_w: float, crop_inf_w: int) -> float:
    """HFOV degrees MoGe should assume for the crop (passed as fov_x).

    Normalized K00 is focal as a fraction of FULL-frame width, and the crop
    shares the parent's physical pixels, so the crop focal in crop-infer
    pixels is K00 * orig_w * (crop_inf_w / crop_nat_w) -- NOT K00 * crop_inf_w
    (that classic slip tells MoGe a ~4x too-wide FOV and shrinks all depths).
    """
    fx = (float(np.asarray(K, dtype=np.float64)[0, 0]) * float(orig_w)
          * (float(crop_inf_w) / float(crop_nat_w)))
    return math.degrees(2.0 * math.atan((float(crop_inf_w) / 2.0) / fx))


def crop_fov_y(K: np.ndarray, crop_infer_w: int, crop_infer_h: int) -> float:
    """VFOV degrees for the crop display record."""
    fx = float(np.asarray(K, dtype=np.float64)[0, 0]) * float(crop_infer_w)
    return math.degrees(2.0 * math.atan((float(crop_infer_h) / 2.0) / fx))


def crop_center_ray(K: np.ndarray, x0: float, y0: float, w: float, h: float,
                    full_w: float, full_h: float) -> np.ndarray:
    """Unit ray (parent CV frame) through the crop center."""
    K = np.asarray(K, dtype=np.float64)
    ccx = (float(x0) + float(w) / 2.0) / float(full_w)
    ccy = (float(y0) + float(h) / 2.0) / float(full_h)
    d = np.array([(ccx - 0.5) / K[0, 0], (ccy - 0.5) / K[1, 1], 1.0])
    return d / np.linalg.norm(d)


def align_rotation(d: np.ndarray) -> np.ndarray:
    """R with R @ (0,0,1) = d. Rodrigues + antiparallel guard."""
    d = np.asarray(d, dtype=np.float64)
    d = d / max(np.linalg.norm(d), 1e-12)
    z = np.array([0.0, 0.0, 1.0])
    v = np.cross(z, d)
    c = float(z @ d)
    if np.linalg.norm(v) < 1e-9:
        return np.eye(3) if c > 0 else np.diag([1.0, -1.0, -1.0])
    vx = np.array([[0.0, -v[2], v[1]], [v[2], 0.0, -v[0]], [-v[1], v[0], 0.0]])
    return np.eye(3) + vx + vx @ vx * (1.0 / (1.0 + c))


def to_parent_frame(points: np.ndarray, R: np.ndarray) -> np.ndarray:
    """Rotate crop-frame points into the parent camera frame (row vectors)."""
    return np.asarray(points) @ np.asarray(R).T


def rotate_normals(normals: np.ndarray, R: np.ndarray) -> np.ndarray:
    n = np.asarray(normals, dtype=np.float64)
    r = (n @ np.asarray(R).T)
    ln = np.linalg.norm(r, axis=-1, keepdims=True)
    return np.where(ln > 1e-9, r / np.maximum(ln, 1e-9), 0.0)


def zoom_to_orig_coords(xs, ys, x0: float, y0: float, crop_nat_w: float,
                        crop_nat_h: float, crop_inf_w: int, crop_inf_h: int):
    """Crop-infer pixel -> native full-res pixel (nearest)."""
    xs = np.asarray(xs, dtype=np.float64)
    ys = np.asarray(ys, dtype=np.float64)
    xo = np.rint(float(x0) + xs * (float(crop_nat_w) / float(crop_inf_w))).astype(np.int64)
    yo = np.rint(float(y0) + ys * (float(crop_nat_h) / float(crop_inf_h))).astype(np.int64)
    return xo, yo


def footprint_keep(xs, ys, fx0: float, fy0: float, fx1: float, fy1: float,
                   dilate_px: float = 4.0):
    """Parent-infer pixels to KEEP: everything outside the dilated crop rect."""
    xs = np.asarray(xs)
    ys = np.asarray(ys)
    keep = ((xs < fx0 - dilate_px) | (xs > fx1 + dilate_px) |
            (ys < fy0 - dilate_px) | (ys > fy1 + dilate_px))
    return keep
