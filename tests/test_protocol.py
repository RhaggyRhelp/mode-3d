"""No-GPU tests: protocol math + .npz payload roundtrip (mirrors daemon->Blender)."""
import io
import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from shared.protocol import fov_y_from_fov_x, clamp_resolution, POINT_SCALE


def test_fov_fix():
    # 90deg HFOV, 16:9-ish 1920x1080: correct ~59deg, linear bug would give 50.6deg
    fy = fov_y_from_fov_x(90.0, 1920, 1080)
    expect = math.degrees(2 * math.atan(math.tan(math.radians(90) / 2) * (1080 / 1920)))
    assert abs(fy - expect) < 1e-6, (fy, expect)
    assert abs(fy - 58.7) < 0.6, fy
    # square stays equal
    assert abs(fov_y_from_fov_x(60.0, 1000, 1000) - 60.0) < 1e-6


def test_clamp_resolution():
    assert clamp_resolution("Low") == 0
    assert clamp_resolution("Medium") == 5
    assert clamp_resolution("High") == 9
    assert clamp_resolution(30) == 9  # Ultra OOM guard
    assert clamp_resolution(-3) == 0


def test_npz_roundtrip_fake():
    H, W = 48, 64
    rng = np.random.default_rng(0)
    points = rng.normal(size=(H, W, 3)).astype(np.float32)
    points[..., 2] = np.abs(points[..., 2]) + 0.5
    depth = points[..., 2].copy()
    normal = np.zeros((H, W, 3), dtype=np.float32)
    normal[..., 2] = 1.0
    mask = np.ones((H, W), dtype=bool)
    K = np.array([[2.0, 0, 0.5], [0, 2.0, 0.5], [0, 0, 1]], dtype=np.float32)
    image = (rng.random((H, W, 3)) * 255).astype(np.uint8)
    buf = io.BytesIO()
    np.savez(buf, points=points, depth=depth, normal=normal, mask=mask,
             intrinsics=K, image=image, fov_x=np.float32(60), fov_y=np.float32(45),
             width=np.int32(W), height=np.int32(H))
    payload = buf.getvalue()
    z = np.load(io.BytesIO(payload), allow_pickle=False)
    assert z["points"].shape == (H, W, 3)
    assert z["mask"].dtype == bool
    # Blender coord swap [x,z,-y] must stay finite
    p = z["points"]
    b = np.stack([p[..., 0], p[..., 2], -p[..., 1]], axis=-1)
    assert np.all(np.isfinite(b))
    # FLOAT_COLOR expansion N*4
    N = H * W
    cols = (z["image"].reshape(-1, 3).astype(np.float32) / 255.0)
    rgba = np.empty((N * 4,), dtype=np.float32)
    rgba[0::4] = cols[:, 0]; rgba[1::4] = cols[:, 1]; rgba[2::4] = cols[:, 2]; rgba[3::4] = 1.0
    assert rgba.shape == (N * 4,)
    assert POINT_SCALE == 1.4


if __name__ == "__main__":
    test_fov_fix()
    test_clamp_resolution()
    test_npz_roundtrip_fake()
    print("protocol tests OK")
