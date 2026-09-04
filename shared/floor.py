"""Floor-plane fit + level matrix. Numpy only (daemon + tests import this).

Convention: MoGe maps are OpenCV camera space (x right, y DOWN, z forward).
Blender splats use (x right, y depth, z up): Pb = S @ Pcv with
S = [[1,0,0],[0,0,1],[0,-1,0]] (a rotation, det +1).

Level target (Blender space): floor plane -> z = 0, floor normal -> +Z.
The returned 4x4 M maps Blender-space points: Pb_level = M @ Pb.
Blender applies M to a parent Empty holding splats + camera (non-destructive).
"""
from __future__ import annotations

import math
import numpy as np

# OpenCV-space "up" (floor normals point image-up). Holds for roll-free photos
# (level, pitched up/down); tubular for rolled/dutch-angle shots -> manual path.
UP_HINT_CV = np.array([0.0, -1.0, 0.0], dtype=np.float64)

# CV -> Blender rotation
S_CV2BL = np.array([[1.0, 0.0, 0.0],
                    [0.0, 0.0, 1.0],
                    [0.0, -1.0, 0.0]], dtype=np.float64)


def rotation_taking_a_to_b(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Rodrigues rotation with antiparallel guard. Inputs need not be unit."""
    a = np.asarray(a, dtype=np.float64)
    b = np.asarray(b, dtype=np.float64)
    na, nb = np.linalg.norm(a), np.linalg.norm(b)
    if na < 1e-12 or nb < 1e-12:
        return np.eye(3)
    a, b = a / na, b / nb
    v = np.cross(a, b)
    c = float(np.dot(a, b))
    if np.linalg.norm(v) < 1e-9:
        if c > 0:
            return np.eye(3)
        # 180 deg: rotate about any axis perpendicular to a
        aux = np.array([1.0, 0.0, 0.0]) if abs(a[0]) < 0.9 else np.array([0.0, 1.0, 0.0])
        v = np.cross(a, aux)
        v = v / np.linalg.norm(v)
        return -np.eye(3) + 2.0 * np.outer(v, v)
    vx = np.array([[0.0, -v[2], v[1]],
                   [v[2], 0.0, -v[0]],
                   [-v[1], v[0], 0.0]])
    return np.eye(3) + vx + vx @ vx * (1.0 / (1.0 + c))


def level_matrix_from_blender_plane(nb: np.ndarray, d: float) -> np.ndarray:
    """M (4x4) taking plane (nb.Bl + d = 0, nb unit) to z = 0, normal -> +Z."""
    nb = np.asarray(nb, dtype=np.float64)
    nb = nb / max(np.linalg.norm(nb), 1e-12)
    R = rotation_taking_a_to_b(nb, np.array([0.0, 0.0, 1.0]))
    M = np.eye(4)
    M[:3, :3] = R
    # Plane is z + d = 0 after R; translating z by +d zeroes the offset.
    M[2, 3] = float(d)
    return M


def fit_floor_plane(points: np.ndarray, normals: np.ndarray, mask: np.ndarray, *,
                    ransac_iters: int = 1500,
                    ransac_cap: int = 60000,
                    dist_factor: float = 0.005,
                    dist_min: float = 0.02,
                    normal_tol_deg: float = 12.0,
                    cone_deg: float = 40.0,
                    min_inlier_frac: float = 0.15,
                    seed: int = 0) -> dict:
    """RANSAC floor fit on MoGe maps. Returns JSON-able stats + level matrix.

    Scoring is SIGNED-normal-gated: candidate normals are flipped toward the up
    hint, and only points whose normals agree (not just parallel) vote. This is
    what keeps ceilings (normals down) from hijacking floor fits indoors.
    """
    points = np.asarray(points, dtype=np.float64)
    normals = np.asarray(normals, dtype=np.float64)
    mask = np.asarray(mask).astype(bool)
    # Accept dense grids (H,W,3)/(H,W) and flat clouds (N,3)/(N,) alike.
    if points.ndim == 3:
        H, W = points.shape[:2]
        points = points.reshape(-1, 3)
        normals = normals.reshape(-1, 3)
        mask = mask.reshape(-1)
    elif points.ndim == 2 and points.shape[1] == 3:
        pass
    else:
        return {"ok": False, "uncertain": True,
                "message": f"points must be HxWx3 or Nx3, got {points.shape}.",
                "n_valid": 0}

    finite = mask & np.isfinite(points).all(axis=-1)
    n_len = np.linalg.norm(normals, axis=-1)
    nok = finite & np.isfinite(normals).all(axis=-1) & (n_len > 0.9) & (n_len < 1.1)
    P = points[nok].reshape(-1, 3)
    N = (normals[nok].reshape(-1, 3) / n_len[nok].reshape(-1, 1))
    n_valid = int(P.shape[0])
    if n_valid < 50:
        return {"ok": False, "uncertain": True,
                "message": f"only {n_valid} usable points (<50).",
                "n_valid": n_valid}

    rng = np.random.default_rng(seed)
    if P.shape[0] > ransac_cap:
        sel = rng.choice(P.shape[0], size=ransac_cap, replace=False)
        Pr, Nr = P[sel], N[sel]
    else:
        Pr, Nr = P, N

    cos_n = math.cos(math.radians(normal_tol_deg))
    cos_cone = math.cos(math.radians(cone_deg))
    med_d = float(np.median(np.linalg.norm(Pr, axis=1)))
    eps = max(dist_min, med_d * dist_factor)

    # floor candidates: normals inside the up cone (signed)
    cand = Nr @ UP_HINT_CV > cos_cone
    if int(cand.sum()) < 3:
        return {"ok": False, "uncertain": True,
                "message": "no normal cluster near camera-up; photo may be rolled or lack flat surfaces — use 3-marker levelling.",
                "n_valid": n_valid}
    cidx = np.nonzero(cand)[0]

    best_inliers = 0
    best = None  # (n_unit, d)
    for _ in range(int(ransac_iters)):
        tri = cidx[rng.choice(cidx.shape[0], size=3, replace=False)]
        p0, p1, p2 = Pr[tri]
        nv = np.cross(p1 - p0, p2 - p0)
        nl = np.linalg.norm(nv)
        if nl < 1e-9:
            continue
        nv = nv / nl
        if float(nv @ UP_HINT_CV) < 0:
            nv = -nv
        if float(nv @ UP_HINT_CV) < cos_cone:
            continue
        d = -float(nv @ p0)
        dist = np.abs(Pr @ nv + d)
        agree = Nr @ nv > cos_n
        inl = int(np.count_nonzero((dist < eps) & agree))
        if inl > best_inliers:
            best_inliers = inl
            best = (nv, d)

    if best is None or best_inliers < 3:
        return {"ok": False, "uncertain": True,
                "message": "RANSAC found no coherent plane — use 3-marker levelling.",
                "n_valid": n_valid}

    # Least-squares refit on full-cloud inliers of the winner (cap for SVD speed)
    nv, d = best
    dist_full = np.abs(P @ nv + d)
    agree_full = N @ nv > cos_n
    inl_full = np.nonzero((dist_full < eps) & agree_full)[0]
    if inl_full.shape[0] > 200000:
        inl_full = rng.choice(inl_full, size=200000, replace=False)
    Q = P[inl_full] - P[inl_full].mean(axis=0)
    _, _, vt = np.linalg.svd(Q, full_matrices=False)
    nv2 = vt[-1]
    if float(nv2 @ UP_HINT_CV) < 0:
        nv2 = -nv2
    d2 = -float(nv2 @ P[inl_full].mean(axis=0))
    # Recenter: subtract the median inlier signed distance so the floor sits on z = 0
    med_off = float(np.median(P[inl_full] @ nv2 + d2))
    d2 -= med_off

    inlier_frac_full = float(np.count_nonzero(
        (np.abs(P @ nv2 + d2) < eps) & (N @ nv2 > cos_n))) / max(n_valid, 1)

    # To Blender space (S is a rotation: offset magnitude preserved)
    nb = S_CV2BL @ nv2
    nb = nb / max(np.linalg.norm(nb), 1e-12)
    M = level_matrix_from_blender_plane(nb, d2)
    tilt_deg = float(np.degrees(np.arccos(np.clip(nb @ np.array([0.0, 0.0, 1.0]), -1.0, 1.0))))
    med_floor_depth = float(np.median(np.linalg.norm(P[inl_full], axis=1))) if inl_full.shape[0] else med_d

    uncertain = bool(inlier_frac_full < min_inlier_frac)
    msg = (f"floor tilt {tilt_deg:.1f}deg, inliers {inlier_frac_full * 100:.1f}%"
           + (" — LOW confidence, verify visually (or use 3 markers)." if uncertain else ""))
    return {"ok": True, "uncertain": uncertain, "message": msg,
            "plane_n_cv": [float(v) for v in nv2],
            "plane_d": float(d2),
            "plane_n_blender": [float(v) for v in nb],
            "matrix_blender": [[float(v) for v in row] for row in M],
            "tilt_deg": tilt_deg, "inlier_frac": inlier_frac_full,
            "n_inliers": int(inl_full.shape[0]), "n_valid": n_valid,
            "eps": float(eps), "med_floor_depth": float(med_floor_depth)}
