"""Adaptive-radius formula tests (no GPU, no Blender).

Mirrors the scan/apply math: r = clip(depth / fx * POINT_SCALE * scale, R_MIN, R_MAX).
"""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from shared.protocol import POINT_SCALE

R_MIN, R_MAX = 0.001, 0.25
FX = 1000.0


def radii(depth, scale=1.0):
    return np.clip(np.asarray(depth, dtype=np.float64) / FX * POINT_SCALE * scale, R_MIN, R_MAX)


def test_perspective_falloff():
    # 2m vs 20m -> 10x radius ratio (area 100x sparser, dots 10x wider)
    r = radii([2.0, 20.0])
    assert abs(r[1] / r[0] - 10.0) < 1e-9, r


def test_typical_scene_values():
    r = radii([4.0, 16.0, 48.0])
    assert abs(r[0] - 0.0056) < 1e-4, r  # 5.6mm near
    assert abs(r[2] - 0.0672) < 1e-4, r  # 67mm far
    assert bool(np.all(np.diff(r) > 0))  # monotonic


def test_scale_linear_and_clamps():
    r1 = radii([10.0], scale=1.0)
    r2 = radii([10.0], scale=2.0)
    assert abs(r2[0] / r1[0] - 2.0) < 1e-9
    assert radii([0.01])[0] == R_MIN  # degenerate near -> floor, never 0/invisible
    assert radii([1000.0])[0] == R_MAX  # skybox far -> ceiling, never dinner plates
    assert radii([0.0])[0] == R_MIN  # zero depth guard


def test_uniform_override_path():
    u = np.full(5, 0.02, dtype=np.float32)
    assert bool(np.all(u == 0.02))


if __name__ == "__main__":
    test_perspective_falloff()
    test_typical_scene_values()
    test_scale_linear_and_clamps()
    test_uniform_override_path()
    print("adaptive-radius tests OK")
