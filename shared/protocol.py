"""Shared constants between daemon (Py3.11) and Blender client (Py3.13). No torch/bpy here."""
from __future__ import annotations

DAEMON_HOST = "127.0.0.1"
DAEMON_PORT = 8766
DAEMON_URL = f"http://{DAEMON_HOST}:{DAEMON_PORT}"

# v3 infer() maps level 0..9 -> num_tokens 1200..3600. Ultra=30 upstream = 9200 tokens -> OOM. Clamped.
RESOLUTION_MAP = {"Low": 0, "Medium": 5, "High": 9}
VALID_LEVELS = ("Low", "Medium", "High")
VALID_MODELS = ("v3", "v2", "v1")
VARIANTS = ("vitl", "vitg")

PRESETS = {
    # fast scrub: v2 + Low is ~3-5x cheaper than v3+High (ViT-L + SSR cost)
    "Draft":       {"model_version": "v2", "variant": "vitl", "resolution_level": "Low",    "refine_steps": 1, "max_size": 1024},
    "Balanced":    {"model_version": "v3", "variant": "vitl", "resolution_level": "High",   "refine_steps": 2, "max_size": 1536},
    "Quality":     {"model_version": "v3", "variant": "vitl", "resolution_level": "High",   "refine_steps": 3, "max_size": 2448},
    # Giant: measured same quality on typical shots, 2.7x VRAM, 1.7x infer.
    # Only for hero shots with hairline structures; evicts vitl while loaded.
    "Giant":       {"model_version": "v3", "variant": "vitg", "resolution_level": "High",   "refine_steps": 3, "max_size": 1536},
    "Max Quality": {"model_version": "v3", "variant": "vitg", "resolution_level": "High",   "refine_steps": 7, "max_size": 4096, "tta": "flip", "zoom": True, "point_budget": 4_000_000},
}

MAX_POINT_BUDGET = 12_000_000  # raised budget limit (was 1.2M)
POINT_SCALE = 1.4              # matches DepthMap3DViewer(point_scale=1.4)
MAX_INFER_DIM = 4096           # support 4K input on 16GB+ GPUs (RTX 4070 Ti SUPER)
DEFAULT_MAX_SIZE = 1536

# Edge handling: depth ltol + normal angular tol (deg), combined as ~(d_edge & n_edge)
EDGE_LTOL = 0.01
NORMAL_EDGE_TOL_DEG = 5.0


def fov_y_from_fov_x(fov_x_deg: float, w: int, h: int) -> float:
    """Correct perspective conversion. Old bug: fov_y = fov_x*(h/w) (linear, wrong)."""
    import math
    fx = math.radians(float(fov_x_deg))
    fy = 2.0 * math.atan(math.tan(fx / 2.0) * (float(h) / float(w)))
    return math.degrees(fy)


def clamp_resolution(level: str | int) -> int:
    if isinstance(level, int):
        return max(0, min(9, level))
    return RESOLUTION_MAP.get(str(level), 9)


def infer_to_orig_coords(xs, ys, w: int, h: int, w0: int, h0: int):
    """Map infer-grid pixel coords to native-image coords (nearest).

    Keep in sync with the copy in blender_extension/moge_splat_studio/__init__.py
    (the addon cannot import this module; it vendors the same 5 lines).
    Uses per-axis ratios (not the resize scale) so rounding differences in
    cv2.resize output dims cannot drift the mapping.
    """
    import numpy as np
    xs = np.asarray(xs)
    ys = np.asarray(ys)
    if w0 == w and h0 == h:
        return xs, ys
    rx = float(w0) / float(w)
    ry = float(h0) / float(h)
    xo = np.clip(np.rint(xs.astype(np.float64) * rx), 0, w0 - 1).astype(np.int64)
    yo = np.clip(np.rint(ys.astype(np.float64) * ry), 0, h0 - 1).astype(np.int64)
    return xo, yo
