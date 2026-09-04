"""Floor-fit tests (no GPU, no Blender). Synthetic tilted room + noise cloud."""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from shared.floor import fit_floor_plane, S_CV2BL, level_matrix_from_blender_plane


def make_room(tilt_deg=0.0, seed=0):
    rng = np.random.default_rng(seed)
    H = W = 120
    P = np.zeros((H, W, 3))
    N = np.zeros((H, W, 3))
    xs = np.linspace(-4, 4, W)
    zs = np.linspace(1, 9, H)
    xx, zz = np.meshgrid(xs, zs)
    P[..., 0] = xx
    P[..., 1] = 2.0 + rng.normal(0, 0.01, (H, W))
    P[..., 2] = zz
    N[...] = (0, -1, 0)
    P[:20, :, 2] = 6.0
    N[:20, :] = (0, 0, -1)       # back wall
    P[:, :15, 0] = -3.0
    N[:, :15] = (1, 0, 0)        # side wall
    N += rng.normal(0, 0.02, (H, W, 3))
    N /= np.linalg.norm(N, axis=-1, keepdims=True)
    if tilt_deg:
        t = np.radians(tilt_deg)
        Rx = np.array([[1, 0, 0], [0, np.cos(t), -np.sin(t)], [0, np.sin(t), np.cos(t)]])
        P = (Rx @ P.reshape(-1, 3).T).T.reshape(H, W, 3)
        N = (Rx @ N.reshape(-1, 3).T).T.reshape(H, W, 3)
    return P, N


def levelled_floor_z(r, P):
    M = np.array(r["matrix_blender"])
    f = (S_CV2BL @ P[60:100, 20:100].reshape(-1, 3).T).T
    fl = (M[:3, :3] @ f.T).T + M[:3, 3]
    return float(np.median(fl[:, 2])), M


def test_flat_room():
    P, N = make_room()
    r = fit_floor_plane(P, N, np.ones(P.shape[:2], bool), seed=0)
    assert r["ok"] and not r["uncertain"], r["message"]
    assert abs(np.array(r["plane_n_cv"]) - np.array([0, -1, 0])).max() < 0.01
    z, _ = levelled_floor_z(r, P)
    assert abs(z) < 0.005, z


def test_tilted_room_detected_and_zeroed():
    P, N = make_room(tilt_deg=20.0)
    r = fit_floor_plane(P, N, np.ones(P.shape[:2], bool), seed=0)
    assert r["ok"] and not r["uncertain"], r["message"]
    assert abs(r["tilt_deg"] - 20.0) < 0.5, r["tilt_deg"]
    z, M = levelled_floor_z(r, P)
    assert abs(z) < 0.005, z
    assert abs(np.linalg.det(M[:3, :3]) - 1.0) < 1e-9  # true rotation


def test_noise_cloud_warns():
    rng = np.random.default_rng(5)
    P = rng.normal(size=(60, 80, 3))
    N = rng.normal(size=(60, 80, 3))
    N /= np.linalg.norm(N, axis=-1, keepdims=True)
    r = fit_floor_plane(P, N, np.ones((60, 80), bool), seed=0, ransac_iters=300)
    assert r["uncertain"], r
    assert r["inlier_frac"] < 0.05


def test_level_matrix_unit():
    M = level_matrix_from_blender_plane(np.array([0.0, 0.0, 1.0]), 1.5)
    p = np.array([1.0, 2.0, -1.5])
    q = M[:3, :3] @ p + M[:3, 3]
    assert abs(q[2]) < 1e-9 and abs(q[0] - 1.0) < 1e-9


def test_flat_cloud_matches_grid():
    from shared.floor import fit_floor_plane as fit
    P, N = make_room(tilt_deg=10.0)
    mk = np.ones(P.shape[:2], bool)
    r_grid = fit(P, N, mk, seed=0)
    n = P.shape[0] * P.shape[1]
    r_flat = fit(P.reshape(n, 3), N.reshape(n, 3), mk.reshape(n), seed=0)
    assert r_flat["ok"] and abs(r_flat["tilt_deg"] - r_grid["tilt_deg"]) < 0.5
    assert abs(r_flat["inlier_frac"] - r_grid["inlier_frac"]) < 0.02


if __name__ == "__main__":
    test_flat_room()
    test_tilted_room_detected_and_zeroed()
    test_noise_cloud_warns()
    test_level_matrix_unit()
    test_flat_cloud_matches_grid()
    print("floor tests OK")
