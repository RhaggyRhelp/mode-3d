"""Flip-ensemble (TTA) fusion. Numpy only.

Mirroring an image mirrors the scene: x -> -x in camera space (x right).
Unflip: fliplr every map, negate points[..., 0] and normals[..., 0].
Fuse onto the BASE frame: median depth (same metric scale, no alignment
needed), points re-projected from fused depth + base intrinsics, normals
averaged + renormalized (fallback to whichever side is valid), mask AND
(cleaner: both views must agree a pixel is valid).
"""
from __future__ import annotations

import numpy as np


def unflip_output(out: dict) -> dict:
    """Mirror a single infer output dict back to base-frame orientation."""
    pts = np.flip(np.asarray(out["points"]), axis=1).copy()
    pts[..., 0] *= -1.0
    dep = np.flip(np.asarray(out["depth"]), axis=1).copy()
    out2 = dict(out)
    out2["points"] = pts
    out2["depth"] = dep
    if out.get("normal") is not None:
        nrm = np.flip(np.asarray(out["normal"]), axis=1).copy()
        nrm[..., 0] *= -1.0
        out2["normal"] = nrm
    if out.get("mask") is not None:
        out2["mask"] = np.flip(np.asarray(out["mask"]), axis=1).copy()
    return out2


def depth_to_points(depth: np.ndarray, K: np.ndarray) -> np.ndarray:
    """Unproject depth with normalized intrinsics K (fx = K[0,0]*W)."""
    depth = np.asarray(depth, dtype=np.float64)
    K = np.asarray(K, dtype=np.float64)
    H, W = depth.shape
    fx, fy = K[0, 0] * W, K[1, 1] * H
    cx, cy = K[0, 2] * W, K[1, 2] * H
    us, vs = np.meshgrid(np.arange(W, dtype=np.float64) + 0.5,
                         np.arange(H, dtype=np.float64) + 0.5)
    z = depth
    x = (us - cx) / fx * z
    y = (vs - cy) / fy * z
    return np.stack([x, y, z], axis=-1)


def resize_grid(arr: np.ndarray, shape, is_mask: bool = False) -> np.ndarray:
    """Numpy-only resize (bilinear, or nearest for masks). No cv2 dependency."""
    arr = np.asarray(arr)
    Ht, Wt = int(shape[0]), int(shape[1])
    Hs, Ws = arr.shape[:2]
    if (Hs, Ws) == (Ht, Wt):
        return arr.copy()
    gy = (np.arange(Ht, dtype=np.float64) + 0.5) * Hs / Ht - 0.5
    gx = (np.arange(Wt, dtype=np.float64) + 0.5) * Ws / Wt - 0.5
    if is_mask:
        yi = np.clip(np.rint(gy).astype(int), 0, Hs - 1)
        xi = np.clip(np.rint(gx).astype(int), 0, Ws - 1)
        return arr[yi[:, None], xi[None, :]].copy()
    y0 = np.clip(np.floor(gy).astype(int), 0, Hs - 2 if Hs > 1 else 0)
    x0 = np.clip(np.floor(gx).astype(int), 0, Ws - 2 if Ws > 1 else 0)
    fy = np.clip(gy - np.floor(gy), 0, 1)[:, None]
    fx = np.clip(gx - np.floor(gx), 0, 1)[None, :]
    a = arr[y0[:, None], x0[None, :]]
    b = arr[y0[:, None], np.minimum(x0[None, :] + 1, Ws - 1)]
    c = arr[np.minimum(y0[:, None] + 1, Hs - 1), x0[None, :]]
    d = arr[np.minimum(y0[:, None] + 1, Hs - 1), np.minimum(x0[None, :] + 1, Ws - 1)]
    if arr.ndim == 3:
        fy = fy[..., None]
        fx = fx[..., None]
    return (a * (1 - fy) * (1 - fx) + b * (1 - fy) * fx
            + c * fy * (1 - fx) + d * fy * fx)


def fuse_views(views: list, K: np.ndarray) -> dict:
    """Median depth over N aligned views (base frame), re-projected points.

    2 views: median == mean (cancels mirror bias, halves jitter variance).
    3+ views: true median, single-view outliers rejected.
    Normals: validity-weighted mean + renormalize. Mask: majority vote.
    """
    K = np.asarray(K, dtype=np.float64)
    ds = [np.asarray(v["depth"], dtype=np.float64) for v in views]
    H, W = ds[0].shape
    stack = np.stack(ds, axis=0)
    with np.errstate(invalid="ignore"):
        depth = np.nanmedian(np.where(np.isfinite(stack), stack, np.nan), axis=0)
    depth = np.where(np.isfinite(depth), depth, np.inf)

    points = depth_to_points(np.where(np.isfinite(depth), depth, 0.0), K)
    points[~np.isfinite(depth)] = np.inf

    fused = dict(views[0])
    fused["depth"] = depth
    fused["points"] = points

    if any(v.get("normal") is not None for v in views):
        acc = np.zeros((H, W, 3))
        cnt = np.zeros((H, W))
        for v in views:
            n = v.get("normal")
            if n is None:
                continue
            na = np.asarray(n, dtype=np.float64)
            good = np.isfinite(na).all(axis=-1) & (np.linalg.norm(na, axis=-1) > 0.5)
            acc[good] += na[good]
            cnt[good] += 1.0
        ln = np.linalg.norm(acc, axis=-1, keepdims=True)
        fused["normal"] = np.where((cnt > 0)[..., None] & (ln > 1e-9),
                                   acc / np.maximum(ln, 1e-9), 0.0)

    masks = [np.asarray(v["mask"]).astype(bool) for v in views if v.get("mask") is not None]
    if masks:
        fused["mask"] = (np.stack(masks).mean(axis=0) > 0.5)
    return fused


def fuse_pair(base: dict, flipped_back: dict, K: np.ndarray) -> dict:
    """Two-view specialization (== mean). Kept for API compat."""
    return fuse_views([base, flipped_back], K)
