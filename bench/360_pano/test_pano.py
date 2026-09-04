"""Pano core tests (no GPU): extraction geometry, scale solve, merge."""
import sys

import numpy as np

sys.path.insert(0, "E:/MOGE")
from shared.pano import (tangent_frame, extract_face, side_overlap_terms,
                         solve_scales, apply_face_transform)


def test_frame_properties():
    I = tangent_frame(0, 0)
    assert np.allclose(I, np.eye(3), atol=1e-12)
    for yaw in (0, 45, 90, 180, 270):
        for pitch in (-90, 0, 90):
            R = tangent_frame(yaw, pitch)
            assert abs(np.linalg.det(R) - 1.0) < 1e-9, (yaw, pitch)
            assert np.allclose(R @ R.T, np.eye(3), atol=1e-9)
    # yaw=90 face forward must point world +x; pitch=+90 looks UP (zenith),
    # pitch=-90 looks DOWN (nadir) in the y-down CV convention.
    assert np.allclose(tangent_frame(90, 0) @ [0, 0, 1], [1, 0, 0], atol=1e-9)
    assert np.allclose(tangent_frame(0, 90) @ [0, 0, 1], [0, -1, 0], atol=1e-9)
    assert np.allclose(tangent_frame(0, -90) @ [0, 0, 1], [0, 1, 0], atol=1e-9)


def test_extract_center_rays():
    H, W = 180, 360
    uu, vv = np.meshgrid(np.arange(W), np.arange(H))
    equi = np.stack([uu % 256, vv % 256, np.zeros((H, W))], axis=-1).astype(np.uint8)
    # yaw=90 center pixel must sample lon=90deg (u=270 -> R=270%256=14), lat=0 (v=90)
    f = extract_face(equi, 90, 0, size=64)
    c = f[32, 32].astype(int)
    assert abs(int(c[0]) - 14) <= 2 and abs(int(c[1]) - 90) <= 2, c
    # pole: center pixel = zenith (top equirect row, G channel ~0 there)
    t = extract_face(equi, 0, 90, size=64)
    assert int(t[32, 32, 1]) <= 2, t[32, 32]
    # pole rim rows must sample near the horizon (elev ~45deg -> v ~ H/4)
    assert 38 <= int(t[0, 32, 1]) <= 54, t[0, 32]
    # pitch=0 matches yaw-only construction (back-compat with tested script)
    f0 = extract_face(equi, 45, 0, size=64)
    assert f0.shape == (64, 64, 3)


def test_solve_recovers_scales():
    rng = np.random.default_rng(0)
    true = np.array([1.0, 1.2, 0.85, 1.1, 0.95, 1.05, 0.9, 1.15])
    terms = []
    for i, j in side_overlap_terms(8):
        # observed log median ratio with noise
        terms.append((i, j, float(np.log(true[i] / true[j]) + rng.normal(0, 0.02)), 1.0))
    s = solve_scales(terms, 8)
    # up to global gauge: ratios must match
    for i, j in side_overlap_terms(8):
        assert abs(np.log(s[i] / s[j]) - np.log(true[i] / true[j])) < 0.05, (i, j)
    assert abs(np.log(s).mean()) < 1e-9  # gauge preserved
    # pole terms pull gently without breaking the ring
    terms_p = terms + []
    s2 = solve_scales(terms, 10, pole_terms=[(8, 0, 0.1), (9, 4, -0.1)])
    assert s2.shape == (10,)
    assert abs(np.log(s2[:8]).mean()) < 0.2


def test_apply_transform():
    P = np.array([[[0.0, 0.0, 5.0]]])
    R = tangent_frame(90, 0)
    q = apply_face_transform(P, R, 2.0)
    assert np.allclose(q[0, 0], [10.0, 0.0, 0.0], atol=1e-9), q


def test_solve_affine_recovers_scale_shift():
    from shared.pano import solve_affine, solve_scales
    rng = np.random.default_rng(1)
    # true per-face (s, t); pair samples share rays, one pair polluted by a
    # doorway (second surface) in 30% of samples
    s_true = np.array([1.0, 1.2, 0.9])
    t_true = np.array([0.0, 0.3, -0.2])
    pairs = []
    truth = rng.uniform(1.5, 4.0, size=2000)
    specs = [(0, 1), (1, 2), (2, 0)]
    for i, j in specs:
        a = truth * s_true[i] + t_true[i] + rng.normal(0, 0.01, truth.shape)
        b = truth * s_true[j] + t_true[j] + rng.normal(0, 0.01, truth.shape)
        a[:600] += 2.0  # doorway contamination in face i only
        pairs.append((i, j, a, b))
    # daemon flow: scalar anchor first (reciprocal depth ratio), then anchored affine
    terms = [(i, j, float(np.log(max(np.median(b), 1e-9) / max(np.median(a), 1e-9))), 1.0)
             for i, j, a, b in pairs]
    s_ref = solve_scales(terms, 3)
    s, t, post = solve_affine(pairs, 3, s_ref=s_ref)
    # NOTE: corrected depth is d' = s*d + t, so the agreeing solution is
    # s_i = K/s_true[i] (inverse!), t_i = -K*tau_i/sigma_i with K set by the
    # face-0 anchor. Assert agreement itself + the anchored absolute level.
    K = s[0] * s_true[0]
    assert np.allclose(s, K / s_true, atol=0.05), (s, s_true)
    assert np.allclose(t, -K * t_true / s_true, atol=0.05), (t, t_true)
    for i, j, a, b in pairs:
        denom = np.maximum(0.5 * (np.abs(a * s[i] + t[i]) + np.abs(b * s[j] + t[j])), 1e-3)
        assert float(np.median(np.abs(a * s[i] + t[i] - (b * s[j] + t[j])) / denom)) < 0.02
    assert all(p < 0.02 for p in post if p == p), post
    # empty input degrades gracefully
    s0, t0, p0 = solve_affine([], 3)
    assert list(s0) == [1.0, 1.0, 1.0] and list(t0) == [0.0, 0.0, 0.0]


def test_flat_wall_no_collapse():
    """Verify that flat walls (narrow depth range) do not collapse into degenerate bas-relief (tiny s, huge t)."""
    from shared.pano import solve_affine, solve_scales
    # 8 faces looking at walls at ~2.0m depth, slight scale differences
    n_faces = 8
    true_scales = np.array([1.0, 1.05, 0.95, 1.02, 0.98, 1.04, 0.96, 1.01])
    pairs = []
    wall_depth = 2.0
    for k in range(n_faces):
        next_k = (k + 1) % n_faces
        # Both measure ~2.0m but with their own scale
        a = np.full(500, wall_depth / true_scales[k]) + np.random.normal(0, 0.02, 500)
        b = np.full(500, wall_depth / true_scales[next_k]) + np.random.normal(0, 0.02, 500)
        pairs.append((k, next_k, a, b))
    terms = [(i, j, float(np.log(max(np.median(b), 1e-9) / max(np.median(a), 1e-9))), 1.0)
             for i, j, a, b in pairs]
    s_ref = solve_scales(terms, n_faces)
    s, t, post = solve_affine(pairs, n_faces, s_ref=s_ref)
    # Scales must stay physically realistic (near 1.0), NOT collapse to 0.2
    assert np.all(s >= 0.7) and np.all(s <= 1.3), s
    # Translation shifts must remain small (< 0.2m)
    assert np.all(np.abs(t) < 0.2), t


def test_exclusive_wedges_tile():
    import math
    from shared.pano import side_wedge_mask, pole_cap_mask, boundary_columns
    H = W = 1024
    m = side_wedge_mask(H, W, 8)
    # kept columns must span yaw_rel in [-22.8, +22.8] (45deg spacing/2 + margin)
    f = (W / 2.0) / math.tan(math.radians(45.0))
    kept = np.nonzero(m[H // 2])[0]
    yaw_kept = np.degrees(np.arctan(((kept + 0.5 - W / 2.0)) / f))
    assert yaw_kept.min() > -23.5 and yaw_kept.max() < 23.5, (yaw_kept.min(), yaw_kept.max())
    assert yaw_kept.min() < -21.5 and yaw_kept.max() > 21.5  # no over-trim
    # 8 wedges at 45deg steps therefore tile 360 with hairline shared edges
    assert 8 * (yaw_kept.max() - yaw_kept.min()) > 360.0
    assert bool(m[:, W // 2].all()) and not bool(m[:, 0].any()) and not bool(m[:, -1].any())
    # pole caps: center kept, corners dropped, meet sides near elev 45
    Rtop = tangent_frame(0, 90)
    cap = pole_cap_mask(H, W, Rtop, True)
    assert bool(cap[H // 2, W // 2]) and not bool(cap[0, 0])
    # 45.5deg cap on a 90deg face keeps all but the corners (~81%)
    assert 0.7 < float(cap.mean()) < 0.9, cap.mean()
    # boundary columns hug the shared ray: last kept cols of face i near
    # u = 0.5 + tan(22.5deg)/2, first kept of face j mirrored
    ci, cj = boundary_columns(8, 90.0, W)
    assert len(ci) > 10 and len(cj) > 10
    import math as _m
    expect = 0.5 + _m.tan(_m.radians(22.5)) / 2.0
    assert abs(ci[-1] / W - expect) < 0.01, (ci[-1], expect)
    assert abs(cj[0] / W - (1 - expect)) < 0.01, (cj[0], expect)
    # strict cube: bands hug the shared edge ray (statistics over the 4deg span)
    e4a, e4b = boundary_columns(4, 90.0, W)
    assert len(e4a) > 0 and len(e4b) > 0
def test_cubemap_4_and_6_geometry():
    from shared.pano import boundary_columns, side_wedge_mask, face_labels, solve_scales, solve_affine
    W = H = 1024
    # 4 walls at 98deg FOV: boundary columns hugging 45deg corners
    ci, cj = boundary_columns(4, 98.0, W)
    assert len(ci) > 20 and len(cj) > 20
    # Wedges tile 360 at 90deg steps (4 walls)
    m4 = side_wedge_mask(H, W, 4, fov_deg=98.0)
    assert bool(m4[:, W // 2].all())  # center column always kept
    f = (W / 2.0) / np.tan(np.radians(98.0 / 2.0))
    kept = np.nonzero(m4[H // 2])[0]
    yaw_kept = np.degrees(np.arctan((kept + 0.5 - W / 2.0) / f))
    assert yaw_kept.min() <= -44.5 and yaw_kept.max() >= 44.5  # covers full 90deg wall
    # Labels
    assert face_labels(4, False) == ["Front", "Right", "Back", "Left"]
    assert face_labels(4, True) == ["Front", "Right", "Back", "Left", "Ceiling", "Floor"]
    # 4-wall scale solve
    true_s = np.array([1.0, 1.1, 0.9, 1.05])
    pairs = []
    for k in range(4):
        next_k = (k + 1) % 4
        a = np.full(300, 2.0 / true_s[k])
        b = np.full(300, 2.0 / true_s[next_k])
        pairs.append((k, next_k, a, b))
    terms = [(i, j, float(np.log(np.median(b) / np.median(a))), 1.0) for i, j, a, b in pairs]
    s_ref = solve_scales(terms, 4)
    s, t, _ = solve_affine(pairs, 4, s_ref=s_ref)
    assert np.allclose(s, s[0] * true_s / true_s[0], atol=0.05)


if __name__ == "__main__":
    test_frame_properties()
    test_extract_center_rays()
    test_solve_recovers_scales()
    test_apply_transform()
    test_exclusive_wedges_tile()
    test_solve_affine_recovers_scale_shift()
    test_flat_wall_no_collapse()
    test_cubemap_4_and_6_geometry()
    print("pano tests OK")
