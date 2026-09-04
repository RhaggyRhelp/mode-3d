"""Panoramic room assembly. Numpy-only (daemon + tests).

Pipeline: equirect -> N tangent faces (yaw ring + poles) -> per-face MoGe
infer at forced 90deg FOV -> per-face metric scales solved jointly (sides via
area overlaps, poles via boundary rings, mean-log gauge) -> merged cloud in
the pano frame (face0 identity) + yaw/pitch camera rig.
"""
from __future__ import annotations

import math
import numpy as np


def tangent_frame(yaw_deg: float, pitch_deg: float = 0.0):
    """Rotation taking face-frame vectors to pano-frame vectors.

    Convention (MoGe CV everywhere): face frame x right, y DOWN image rows,
    z forward along the face-center ray. Pano frame = face0 frame.
    pitch > 0 looks UP (toward zenith): R @ (0,0,1) = (0,-sin p, cos p).
    """
    t = math.radians(float(yaw_deg))
    p = math.radians(float(pitch_deg))
    Rx = np.array([[1.0, 0.0, 0.0],
                   [0.0, math.cos(p), -math.sin(p)],
                   [0.0, math.sin(p), math.cos(p)]])
    Ry = np.array([[math.cos(t), 0.0, math.sin(t)],
                   [0.0, 1.0, 0.0],
                   [-math.sin(t), 0.0, math.cos(t)]])
    return Ry @ Rx


def extract_face(equi: np.ndarray, yaw_deg: float, pitch_deg: float = 0.0,
                 fov_deg: float = 90.0, size: int = 2048,
                 interpolation=None) -> np.ndarray:
    """Gnomonic tangent view. cv2 remap if available, else numpy bilinear."""
    H, W = equi.shape[:2]
    f = (size / 2.0) / math.tan(math.radians(fov_deg / 2.0))
    ys, xs = np.mgrid[0:size, 0:size].astype(np.float64)
    # MoGe CV: x right, y DOWN rows, z forward. R maps face -> pano frame.
    rx = (xs + 0.5 - size / 2.0) / f
    ry = (ys + 0.5 - size / 2.0) / f
    v = np.stack([rx, ry, np.ones_like(rx)], axis=-1)
    R = tangent_frame(yaw_deg, pitch_deg)
    d = v @ R.T
    n = np.linalg.norm(d, axis=-1, keepdims=True)
    lon = np.arctan2(d[..., 0], d[..., 2])
    # elevation above horizon: up is pano -y, so el = asin(-d.y)
    lat = np.arcsin(np.clip(-d[..., 1] / np.maximum(n[..., 0], 1e-12), -1.0, 1.0))
    u = (lon / (2 * math.pi) + 0.5) * W
    vv = (0.5 - lat / math.pi) * H
    try:
        import cv2 as _cv2
        if interpolation is None:
            interpolation = _cv2.INTER_LINEAR
        return _cv2.remap(equi, u.astype(np.float32), vv.astype(np.float32),
                          interpolation=interpolation, borderMode=_cv2.BORDER_WRAP)
    except ImportError:
        return _bilinear(equi, u, vv)


def _bilinear(img: np.ndarray, u: np.ndarray, v: np.ndarray) -> np.ndarray:
    H, W = img.shape[:2]
    u = np.clip(u, 0, W - 1.001)
    v = np.clip(v, 0, H - 1.001)
    x0 = np.floor(u).astype(int)
    y0 = np.floor(v).astype(int)
    fx = (u - x0)[..., None] if img.ndim == 3 else (u - x0)
    fy = (v - y0)[..., None] if img.ndim == 3 else (v - y0)
    a = img[y0, x0]
    b = img[y0, np.minimum(x0 + 1, W - 1)]
    c = img[np.minimum(y0 + 1, H - 1), x0]
    d = img[np.minimum(y0 + 1, H - 1), np.minimum(x0 + 1, W - 1)]
    return (a * (1 - fy) * (1 - fx) + b * (1 - fy) * fx
            + c * fy * (1 - fx) + d * fy * fx).astype(img.dtype)


def side_overlap_terms(n_yaw: int = 8):
    """Adjacent side-face pairs for the scale solve."""
    return [(i, (i + 1) % n_yaw) for i in range(n_yaw)]


def _u_of_yaw_rel(yaw_rel_deg, fov_deg: float):
    t = np.tan(np.radians(np.asarray(yaw_rel_deg, dtype=np.float64)))
    h = np.tan(np.radians(float(fov_deg) / 2.0))
    return 0.5 + t / (2.0 * h)


def match_columns(n_yaw: int, fov_deg: float, w: int, frac: float = 0.5):
    """Corresponding column index arrays for adjacent side faces.

    Overlap wedge middle `frac` (edge distortion avoided). Exact at the
    horizon; off by ~1-2deg at extreme rows for 90deg faces -- median ratios
    over ~1M px don't care. Returns (cols_i, cols_j), possibly empty when
    spacing >= fov (e.g. strict 4-cube: no shared pixels by construction).
    """
    spacing = 360.0 / float(n_yaw)
    half = float(fov_deg) / 2.0
    if spacing >= float(fov_deg) - 1e-9:
        return np.zeros(0, dtype=int), np.zeros(0, dtype=int)
    # wedge in face-i-relative yaw: [spacing - half, +half]; take middle frac
    lo, hi = spacing - half, half
    mid, span = (lo + hi) / 2.0, (hi - lo) * float(frac)
    MU = 256
    yr = np.linspace(mid - span / 2.0, mid + span / 2.0, MU)
    ui = np.clip((_u_of_yaw_rel(yr, fov_deg) * w).astype(int), 0, w - 1)
    uj = np.clip((_u_of_yaw_rel(yr - spacing, fov_deg) * w).astype(int), 0, w - 1)
    return np.unique(ui), np.unique(uj)


def boundary_columns(n_yaw: int, fov_deg: float, w: int, inset_deg: float = 0.0):
    """Column bands hugging the shared boundary ray between adjacent sides.

    Returns (cols_i, cols_j): the last kept columns of face i and the first
    kept columns of face j. Optimizing THESE (not mid-overlap) aligns what the
    eye actually sees at the handoff. inset_deg pulls inside the kept edge.
    """
    spacing = 360.0 / float(n_yaw)
    half = float(fov_deg) / 2.0
    b = spacing / 2.0  # boundary ray in face-relative yaw
    if b > half + 1e-9:
        return np.zeros(0, dtype=int), np.zeros(0, dtype=int)
    MU = 512
    # face i side: yaw_rel in [b - span, b]; face j side mirrored
    span = min(4.0, half - b + 4.0)
    yr_i = np.linspace(b - span, b - float(inset_deg), MU)
    yr_j = np.linspace(-b + float(inset_deg), -b + span, MU)
    ui = np.clip((_u_of_yaw_rel(yr_i, fov_deg) * w).astype(int), 0, w - 1)
    uj = np.clip((_u_of_yaw_rel(yr_j, fov_deg) * w).astype(int), 0, w - 1)
    return np.unique(ui), np.unique(uj)


def pole_wedge_mask(h: int, w: int, R, yaw_center_deg: float, half_width_deg: float = 67.5,
                    rim_px: int = 40):
    """Rim-band pixels of a pole face facing one side (yaw wedge around center).

    R: face->pano rotation used for that pole face.
    """
    ys, xs = np.mgrid[0:h, 0:w]
    rim = (ys < rim_px) | (ys >= h - rim_px) | (xs < rim_px) | (xs >= w - rim_px)
    if not rim.any():
        return rim
    # NOTE: yaw = atan2(dx, dz) is invariant to the y-sign convention, so the
    # legacy negated ry here is harmless (only yaw is used, never elevation).
    f = 1.0  # direction only; focal cancels in atan2
    rx = (xs + 0.5 - w / 2.0)
    ry = -(ys + 0.5 - h / 2.0)
    v = np.stack([rx, ry, np.ones_like(rx)], axis=-1).reshape(-1, 3)
    d = (v @ np.asarray(R).T).reshape(h, w, 3)
    yaw = np.degrees(np.arctan2(d[..., 0], d[..., 2]))
    diff = (yaw - float(yaw_center_deg) + 180.0) % 360.0 - 180.0
    return rim & (np.abs(diff) < float(half_width_deg))


def solve_scales(log_ratios: list, n_faces: int, pole_terms: list | None = None,
                 pole_weight: float = 0.25) -> np.ndarray:
    """Least-squares per-face log-scales from pairwise log median ratios.

    log_ratios: [(i, j, log(med_i/med_j), weight)]. Gauge: mean(log s) = 0
    (global scale preserved). Returns s (linear scales, mean-log 1.0).
    """
    rows, rhs, wts = [], [], []
    for i, j, lr, w in log_ratios:
        row = np.zeros(n_faces)
        row[i] = 1.0
        row[j] = -1.0
        rows.append(row)
        rhs.append(lr)
        wts.append(w)
    for i, j, lr in (pole_terms or []):
        row = np.zeros(n_faces)
        row[i] = 1.0
        row[j] = -1.0
        rows.append(row)
        rhs.append(lr)
        wts.append(pole_weight)
    rows.append(np.ones(n_faces) / n_faces)  # gauge: mean log-scale 0
    rhs.append(0.0)
    wts.append(1.0)
    A = np.array(rows) * np.array(wts)[:, None]
    b = np.array(rhs) * np.array(wts)
    x, *_ = np.linalg.lstsq(A, b, rcond=None)
    return np.exp(x - x.mean())


def apply_face_transform(points: np.ndarray, R: np.ndarray, scale: float) -> np.ndarray:
    """Face-frame points -> pano frame (row vectors): P @ R.T * s."""
    return (np.asarray(points, dtype=np.float64) @ np.asarray(R).T) * float(scale)


def solve_affine(pairs: list, n_faces: int, s_ref=None, ransac_iters: int = 300,
                 inlier_tol: float = 0.06):
    """Joint per-face scale+shift from PAIRED boundary samples.

    pairs: [(i, j, a, b)] with a, b same-length valid depth samples on shared
    rays (a from face i, b from face j). Model: a*s_i + t_i ~= b*s_j + t_j.
    RANSAC over minimal subsets + refit on consensus inliers (inlier_tol
    relative residual), so content edges near boundaries can't steer
    selection the way trim-from-a-fit can.

    Anchoring (read carefully): homogeneous data equations always admit the
    trivial s=t=0 collapse, and mean() gauges can pick a reciprocal trap, so
    NEITHER is used. Instead face 0 is HARD-anchored to the trusted scalar
    solution (s_0 = s_ref[0], t_0 = 0); all other faces solve relative to it
    through the connected pair graph. Absolute level therefore equals the
    scalar path (documented, honest); only relative agreement affects seams.
    Returns (s, t, post): post[k] = median |rel| residual of pair k inliers.
    """
    n = int(n_faces)
    data = []
    for i, j, a, b in pairs:
        a = np.asarray(a, dtype=np.float64).ravel()
        b = np.asarray(b, dtype=np.float64).ravel()
        ok = np.isfinite(a) & np.isfinite(b) & (a > 0.05) & (b > 0.05)
        a, b = a[ok], b[ok]
        if a.shape[0] >= 50:
            data.append((int(i), int(j), a, b))
    S_LO, S_HI, T_LIM = 0.5, 2.0, 0.6
    s = np.ones(n)
    if s_ref is not None:
        s = np.clip(np.asarray(s_ref, dtype=np.float64), S_LO, S_HI)
        if s.shape[0] != n:
            s = np.ones(n)
    t = np.zeros(n)
    if not data:
        return s, t, []
    s_init = s.copy()
    involved = sorted({i for d in data for i in d[:2] if i != 0} | {0})
    # free unknowns: faces 1..n-1 (face 0 anchored). col index helper:
    def _col(face, is_t):
        return None if face == 0 else (face - 1 + (0 if not is_t else (n - 1)))
    nvars = 2 * (n - 1)
    def _build(idxs):
        rows, rhs = [], []
        for (i, j, a, b), k in zip(data, idxs):
            aa, bb = a[k], b[k]
            m = len(aa)
            if m == 0:
                continue
            r = np.zeros((m, nvars))
            y = bb * s_init[j] - aa * s_init[i]
            ci = _col(i, False)
            if ci is not None:
                r[:, ci] = aa
            ci = _col(i, True)
            if ci is not None:
                r[:, ci] = 1.0
            cj = _col(j, False)
            if cj is not None:
                r[:, cj] = -bb
            cj = _col(j, True)
            if cj is not None:
                r[:, cj] = -1.0
            rows.append(r)
            rhs.append(y)
        if not rows:
            return None, None
        reg = np.diag(np.concatenate([np.full(n - 1, 0.5), np.full(n - 1, 2.0)]))
        return np.vstack([np.vstack(rows), reg]), np.concatenate([np.concatenate(rhs), np.zeros(nvars)])

    def _score(sv, tv):
        tot, inl = 0, 0
        for i, j, a, b in data:
            pred = a * sv[i] + tv[i] - (b * sv[j] + tv[j])
            denom = np.maximum(0.5 * (np.abs(a * sv[i] + tv[i]) + np.abs(b * sv[j] + tv[j])), 1e-3)
            rr = np.abs(pred) / denom
            inl += int((rr < float(inlier_tol)).sum())
            tot += len(rr)
        return inl, tot

    rng = np.random.default_rng(0)
    npairs = len(data)
    per = max(2, min(5, (2 * max(nvars, 1) + npairs - 1) // max(npairs, 1)))
    best, best_inl, best_pen = None, -1, float("inf")

    for _ in range(max(50, int(ransac_iters))):
        idxs = []
        for _, _, a, _ in data:
            m = len(a)
            idxs.append(rng.choice(m, size=min(m, per), replace=False))
        A, y = _build(idxs)
        if A is None:
            continue
        try:
            x, *_ = np.linalg.lstsq(A, y, rcond=None)
        except Exception:
            continue
        sv = s_init.copy()
        tv = np.zeros(n)
        sv[1:] = np.clip(s_init[1:] + x[:n - 1], S_LO, S_HI)
        tv[1:] = np.clip(x[n - 1:], -T_LIM, T_LIM)
        inl, tot = _score(sv, tv)
        pen = float(np.sum((sv[1:] - s_init[1:]) ** 2) + 0.5 * np.sum(tv[1:] ** 2))
        if inl > best_inl or (inl == best_inl and pen < best_pen):
            best_inl, best_pen = inl, pen
            best = (sv, tv)
    if best is None:
        return s_init, np.zeros(n), []
    # Safety net: consensus below 40% means RANSAC found no agreement --
    # return the scalar anchor untouched with zero shift rather than a degenerate fit.
    _, tot_all = _score(s_init, np.zeros(n))
    if best_inl < 0.4 * max(tot_all, 1):
        return s_init, np.zeros(n), [float("nan")] * len(data)
    s, t = best
    idxs = []
    for i, j, a, b in data:
        pred = a * s[i] + t[i] - (b * s[j] + t[j])
        denom = np.maximum(0.5 * (np.abs(a * s[i] + t[i]) + np.abs(b * s[j] + t[j])), 1e-3)
        idxs.append(np.nonzero(np.abs(pred) / denom < float(inlier_tol))[0])
    A, y = _build(idxs)
    if A is not None:
        try:
            x, *_ = np.linalg.lstsq(A, y, rcond=None)
            s[1:] = np.clip(s_init[1:] + x[:n - 1], S_LO, S_HI)
            t[1:] = np.clip(x[n - 1:], -T_LIM, T_LIM)
        except Exception:
            pass
    post = []
    for i, j, a, b in data:
        pred = a * s[i] + t[i] - (b * s[j] + t[j])
        denom = np.maximum(0.5 * (np.abs(a * s[i] + t[i]) + np.abs(b * s[j] + t[j])), 1e-3)
        rr = np.abs(pred) / denom
        inl = rr < float(inlier_tol)
        post.append(float(np.median(rr[inl])) if inl.any() else float("nan"))
    return s, t, post


def side_wedge_mask(h: int, w: int, n_yaw: int, fov_deg: float = 90.0,
                    margin_deg: float = 0.3) -> np.ndarray:
    """Exclusive display wedge for a side face: |yaw_rel| <= spacing/2 + margin.

    Adjacent wedges tile 360deg with shared boundary rays: where one cloud
    ends, the neighbor picks up. No rendered overlap -> no doubling, ever.
    """
    spacing = 360.0 / float(n_yaw)
    half = spacing / 2.0 + float(margin_deg)
    xs = (np.arange(w, dtype=np.float64) + 0.5 - w / 2.0)
    # yaw_rel per column (gnomonic: yaw = atan(x / focal), focal = (w/2)/tan(fov/2))
    focal = (w / 2.0) / math.tan(math.radians(float(fov_deg) / 2.0))
    yaw_rel = np.degrees(np.arctan(xs / focal))
    keep_cols = np.abs(yaw_rel) <= half
    return np.broadcast_to(keep_cols[None, :], (h, w)).copy()


def pole_cap_mask(h: int, w: int, R, top: bool, fov_deg: float = 90.0, cap_deg: float = 45.5) -> np.ndarray:
    """Polar cap for a pole face: angular radius from the pole axis <= cap.

    Meets side wedges (full-height, elev +-45) at the 45deg parallel.
    """
    ys, xs = np.mgrid[0:h, 0:w].astype(np.float64)
    # face-frame rays (focal-normalized, MoGe CV: x right, y down, z forward)
    foc = (w / 2.0) / math.tan(math.radians(float(fov_deg) / 2.0))
    rx = (xs + 0.5 - w / 2.0) / foc
    ry = (ys + 0.5 - h / 2.0) / foc
    v = np.stack([rx, ry, np.ones_like(rx)], axis=-1).reshape(-1, 3)
    d = (v @ np.asarray(R).T).reshape(h, w, 3)
    dn = np.linalg.norm(d, axis=-1)
    axis = np.array([0.0, -1.0, 0.0]) if top else np.array([0.0, 1.0, 0.0])
    cosang = (d.reshape(-1, 3) @ axis / np.maximum(dn.reshape(-1), 1e-12)).reshape(h, w)
    return cosang >= math.cos(math.radians(float(cap_deg)))


def face_labels(n_yaw: int, include_poles: bool) -> list[str]:
    """Semantic names for face collections and cameras."""
    if n_yaw == 4:
        names = ["Front", "Right", "Back", "Left"]
    elif n_yaw == 6:
        names = ["Front", "Front-Right", "Back-Right", "Back", "Back-Left", "Front-Left"]
    else:
        names = [f"Side {i}" for i in range(n_yaw)]
    if include_poles:
        names += ["Ceiling", "Floor"]
    return names
