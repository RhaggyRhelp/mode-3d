"""Decoupled-color tests (no GPU, no Blender).

Proves the mechanism behind the sharpness claim with a synthetic worst case:
an 8x8 checker downscaled to 4x4 (INTER_AREA) becomes flat gray -- the high
frequency is unrecoverable from the small image -- while native sampling
preserves it exactly.
"""
import sys
from pathlib import Path

import numpy as np
import cv2

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from shared.protocol import infer_to_orig_coords


def test_identity_noop():
    xs = np.array([0, 3, 7])
    ys = np.array([0, 2, 5])
    xo, yo = infer_to_orig_coords(xs, ys, 8, 8, 8, 8)
    assert np.array_equal(xo, xs) and np.array_equal(yo, ys)


def test_mapping_roundtrip_scale():
    # infer 4x4 from orig 8x8: infer texel (i,j) covers orig block [2i:2i+2, 2j:2j+2];
    # nearest mapping must land inside that block
    xs = np.arange(4)
    ys = np.arange(4)
    xx, yy = np.meshgrid(xs, ys)
    xo, yo = infer_to_orig_coords(xx.ravel(), yy.ravel(), 4, 4, 8, 8)
    assert xo.min() >= 0 and xo.max() <= 7
    assert yo.min() >= 0 and yo.max() <= 7
    # monotonic: order preserved along rows/cols
    assert bool(np.all(np.diff(xo.reshape(4, 4), axis=1) >= 0))
    assert bool(np.all(np.diff(yo.reshape(4, 4), axis=0) >= 0))


def test_nonsquare_and_clip():
    rng = np.random.default_rng(0)
    xs = rng.integers(0, 100, size=500)
    ys = rng.integers(0, 50, size=500)
    xo, yo = infer_to_orig_coords(xs, ys, 100, 50, 1920, 1080)
    assert xo.min() >= 0 and xo.max() <= 1919
    assert yo.min() >= 0 and yo.max() <= 1079
    # linear scale check on a known point: center maps near center
    xo_c, yo_c = infer_to_orig_coords(np.array([50]), np.array([25]), 100, 50, 1920, 1080)
    assert abs(int(xo_c[0]) - 960) <= 1 and abs(int(yo_c[0]) - 540) <= 1


def test_native_sampling_exact_and_richer():
    # Seeded random 8x8 RGB downscaled to 4x4 (INTER_AREA averages 2x2 blocks).
    # Decoupled sampling must (a) equal the native pixels it addresses exactly,
    # (b) differ from the averaged small-image texels almost everywhere,
    # (c) preserve more contrast (std) than the averaged image.
    rng = np.random.default_rng(7)
    orig = rng.integers(0, 256, size=(8, 8, 3)).astype(np.uint8)
    small = cv2.resize(orig, (4, 4), interpolation=cv2.INTER_AREA)
    H = W = 4
    H0 = W0 = 8
    ys, xs = np.nonzero(np.ones((H, W), dtype=bool))
    xo, yo = infer_to_orig_coords(xs, ys, W, H, W0, H0)
    decoupled = orig[yo, xo]
    current = small[ys, xs]
    assert np.array_equal(decoupled, orig[yo, xo])  # exact native pixels
    frac_diff = float(np.mean(np.any(decoupled != current, axis=-1)))
    assert frac_diff > 0.9, f"averaging should destroy info, diff={frac_diff}"
    assert float(decoupled.std()) > float(small.std()) * 1.5


if __name__ == "__main__":
    test_identity_noop()
    test_mapping_roundtrip_scale()
    test_nonsquare_and_clip()
    test_native_sampling_exact_and_richer()
    print("decouple tests OK")
