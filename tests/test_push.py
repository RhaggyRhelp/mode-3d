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


def test_meta_summarize():
    meta = {"image_file": "a.jpg", "orig_width": 4080, "orig_height": 3072,
            "image_width": 2047, "image_height": 1541, "model_version": "v3",
            "variant": "vitg", "tta": "flip", "fov_x": 70.0, "fov_y": 55.0,
            "fov_src": "exif", "min_depth": 1.0, "max_depth": 5.0,
            "points": 1234567, "color_src": "native", "radius_src": "adaptive",
            "level": "tilt was 2.0deg"}
    rows = summarize(meta)
    assert len(rows) == 7, len(rows)
    assert rows[1][2].startswith("v3/vitg +TTA:flip"), rows[1]
    assert rows == summarize(dict(meta))  # deterministic
    assert summarize({}) == [] and summarize(None) == []


if __name__ == "__main__":
    test_unflip_mirrors_x()
    test_fuse_two_view_mean_and_three_view_median()
    test_depth_to_points_center_ray()
    test_exif_roundtrip()
    test_meta_summarize()
    print("push tests OK")
