"""Push-limits shared-math tests (no GPU, no Blender)."""
import io
import sys
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
from shared.tta import unflip_output, fuse_pair, fuse_views, depth_to_points
from shared.exif import fov_x_from_exif
from shared.zoom import (crop_fov_x, crop_center_ray, align_rotation,
                         to_parent_frame, rotate_normals, zoom_to_orig_coords,
                         footprint_keep)
from shared.meta import summarize


def test_unflip_mirrors_x():
    H = W = 8
    P = np.zeros((H, W, 3))
    P[..., 0] = np.linspace(-1, 1, W)[None, :].repeat(H, axis=0)
    P[..., 2] = 2.0
    out = {"points": P, "depth": P[..., 2].copy(),
           "normal": np.stack([P[..., 0], np.zeros((H, W)), np.ones((H, W))], -1),
           "mask": np.ones((H, W), bool)}
    u = unflip_output(out)
    # double mirror = identity
    u2 = unflip_output(u)
    assert np.allclose(u2["points"], P), "mirror twice must restore"
    assert np.allclose(u2["normal"], out["normal"])
    # single mirror negates x, keeps depth
    assert np.allclose(u["points"][..., 0], -P[..., 0][:, ::-1])
    assert np.allclose(u["depth"], P[..., 2][:, ::-1])


def test_fuse_two_view_mean_and_three_view_median():
    from shared.tta import fuse_views, resize_grid
    H = W = 8
    K = np.array([[2.0, 0, 0.5], [0, 2.0, 0.5], [0, 0, 1.0]])
    n = np.zeros((H, W, 3))
    n[..., 2] = 1.0

    def view(depth_val, outlier=None):
        d = np.full((H, W), depth_val)
        if outlier:
            d[outlier] = 9.0
        return {"points": depth_to_points(d, K), "depth": d, "normal": n.copy(),
                "mask": np.ones((H, W), bool)}

    # 2 views: median == mean (documented: cancels mirror bias, halves jitter)
    fu2 = fuse_views([view(3.0, (0, 0)), view(3.0)], K)
    assert abs(float(fu2["depth"][0, 0]) - 6.0) < 1e-9, fu2["depth"][0, 0]
    assert bool(fu2["mask"].all())
    # 3 views: true median rejects the single-view outlier
    fu3 = fuse_views([view(3.0, (0, 0)), view(3.0), view(3.0)], K)
    assert abs(float(fu3["depth"][0, 0]) - 3.0) < 1e-9, fu3["depth"][0, 0]
    assert abs(float(fu3["depth"].mean()) - 3.0) < 1e-9
    assert abs(np.linalg.norm(fu3["normal"][4, 4]) - 1.0) < 1e-9
    # disagreement: one side invalid -> take the other
    d_bad = np.full((H, W), 3.0)
    d_bad[1, 1] = np.inf
    fu4 = fuse_views([view(3.0), {"points": depth_to_points(d_bad, K), "depth": d_bad,
                                  "normal": n.copy(), "mask": np.ones((H, W), bool)}], K)
    assert abs(float(fu4["depth"][1, 1]) - 3.0) < 1e-9
    # resize_grid: identity, nearest masks, bilinear values
    assert np.array_equal(resize_grid(n, (8, 8)), n)
    m = (np.indices((8, 8)).sum(axis=0) % 2 == 0)
    assert np.array_equal(resize_grid(m, (8, 8), is_mask=True), m)
    up = resize_grid(np.arange(4, dtype=float).reshape(2, 2), (4, 4))
    assert up.shape == (4, 4) and up.min() >= 0.0 and up.max() <= 3.0


def test_depth_to_points_center_ray():
    K = np.array([[2.0, 0, 0.5], [0, 2.0, 0.5], [0, 0, 1.0]])
    p = depth_to_points(np.full((4, 6), 5.0), K)
    assert p.shape == (4, 6, 3)
    c = p[2, 3]  # near-center pixel
    assert abs(c[2] - 5.0) < 1e-9 and abs(c[0]) < 0.5 and abs(c[1]) < 0.5


def test_exif_roundtrip():
    from PIL import Image as PILImage
    im = PILImage.new("RGB", (64, 48), (10, 20, 30))
    ex = PILImage.Exif()
    ex.get_ifd(0x8769)[41989] = 26  # 26mm equiv, nested like phones write it
    buf = io.BytesIO()
    im.save(buf, format="JPEG", exif=ex)
    fov = fov_x_from_exif(buf.getvalue())
    import math
    expect = math.degrees(2 * math.atan(18.0 / 26.0))
    assert fov is not None and abs(fov - expect) < 1e-6, (fov, expect)
    # no exif -> None (never crash the scan)
    buf2 = io.BytesIO()
    PILImage.new("RGB", (8, 8)).save(buf2, format="PNG")
    assert fov_x_from_exif(buf2.getvalue()) is None
    assert fov_x_from_exif(b"garbage-bytes") is None


def test_zoom_center_crop_identity():
    import math
    K = np.array([[2.0, 0, 0.5], [0, 2.0, 0.5], [0, 0, 1.0]])
    parent_fov = 2 * math.degrees(math.atan(1000.0 / 4000.0))
    # full frame as crop == parent FOV
    assert abs(crop_fov_x(K, 2000, 2000, 2000) - parent_fov) < 1e-9
    # half-width crop is narrower, and resize preserves angle
    half = crop_fov_x(K, 2000, 1000, 1000)
    assert half < parent_fov
    assert abs(crop_fov_x(K, 2000, 1000, 500) - half) < 1e-9
    # regression: the old formula (K00 * crop_inf_w) overstated FOV ~2x here
    wrong = 2 * math.degrees(math.atan(500.0 / 2000.0))
    assert wrong > 1.9 * half, (wrong, half)
    d = crop_center_ray(K, 480, 270, 960, 540, 1920, 1080)  # centered crop
    assert np.allclose(d, [0, 0, 1], atol=1e-9), d
    R = align_rotation(d)
    assert np.allclose(R, np.eye(3), atol=1e-9)
    # off-center crop: ray tilts correctly, R maps +Z onto it
    d2 = crop_center_ray(K, 960, 0, 960, 1080, 1920, 1080)  # right half
    assert d2[0] > 0.1 and abs(d2[1]) < 1e-9, d2
    R2 = align_rotation(d2)
    assert np.allclose(R2 @ np.array([0.0, 0.0, 1.0]), d2, atol=1e-9)
    assert abs(np.linalg.det(R2) - 1.0) < 1e-9
    # points + normals rotate together
    p = np.array([[[0.0, 0.0, 5.0]]])
    assert np.allclose(to_parent_frame(p, R2)[0, 0], d2 * 5.0, atol=1e-9)
    assert np.allclose(rotate_normals(np.array([[[0.0, 0.0, 1.0]]]), R2)[0, 0], d2, atol=1e-9)


def test_zoom_mapping_and_footprint():
    xo, yo = zoom_to_orig_coords(np.array([0, 500]), np.array([0, 250]),
                                 960, 0, 960, 1080, 960, 540)
    assert list(xo) == [960, 1460] and list(yo) == [0, 500], (xo, yo)
    xs = np.array([10, 150, 900])
    ys = np.array([10, 150, 700])
    # footprint rect in parent-infer grid, say x 100..200, y 100..200
    keep = footprint_keep(xs, ys, 100, 100, 200, 200)
    assert list(keep) == [True, False, True], keep
    # dilation: just outside the rect is still dropped
    keep2 = footprint_keep(np.array([202]), np.array([150]), 100, 100, 200, 200,
                           dilate_px=4.0)
    assert list(keep2) == [False], keep2


def test_meta_summarize():
    meta = {"image_file": "a.jpg", "orig_width": 4080, "orig_height": 3072,
            "image_width": 2047, "image_height": 1541, "model_version": "v3",
            "variant": "vitg", "tta": "flip", "fov_x": 70.0, "fov_y": 55.0,
            "fov_src": "exif", "min_depth": 1.0, "max_depth": 5.0,
            "points": 1234567, "color_src": "native", "radius_src": "adaptive",
            "zoom": {"points": 999, "seam_rel": "1.2%"},
            "level": "tilt was 2.0deg"}
    rows = summarize(meta)
    assert len(rows) == 8, len(rows)
    assert rows[1][2].startswith("v3/vitg +TTA:flip"), rows[1]
    assert rows == summarize(dict(meta))  # deterministic
    assert summarize({}) == [] and summarize(None) == []


if __name__ == "__main__":
    test_unflip_mirrors_x()
    test_fuse_two_view_mean_and_three_view_median()
    test_depth_to_points_center_ray()
    test_exif_roundtrip()
    test_zoom_center_crop_identity()
    test_zoom_mapping_and_footprint()
    test_meta_summarize()
    print("push tests OK")
