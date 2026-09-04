"""MoGe warm GPU daemon. Keeps MoGe-3/2/1 in VRAM, serves .npz over localhost.

Run:
  python daemon/launch_daemon.py
  or daemon/launch_daemon.bat

Protocol: POST /infer (multipart: image file + form fields) -> application/x-numpy-archive (.npz, uncompressed).
_npz keys: points, depth, normal, mask, intrinsics, image, fov_x, fov_y, width, height,
orig_width, orig_height (decoupled full-res color: sample native file at xs*orig_w/w).
"""
from __future__ import annotations

import os
os.environ.setdefault("OPENCV_IO_ENABLE_OPENEXR", "1")

import io
import sys
import time
import math
import traceback
from pathlib import Path
from typing import Optional

import numpy as np
import cv2
import torch

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

def _resolve_moge_import():
    try:
        import moge
        return
    except ImportError:
        pass
    env = os.environ.get("MOGE_REPO", "").strip().strip('"')
    if env and Path(env).exists():
        if env not in sys.path:
            sys.path.insert(0, env)
        return
    candidates = [
        REPO_ROOT / "MoGe",
        REPO_ROOT.parent / "MoGe",
        Path.cwd() / "MoGe",
        Path.home() / "MoGe",
        Path.home() / "Documents" / "MoGe",
    ]
    for c in candidates:
        if c.exists() and (c / "moge").exists():
            if str(c) not in sys.path:
                sys.path.insert(0, str(c))
            return

_resolve_moge_import()

import flex_gemm
flex_gemm.config.AUTOTUNE_MODE = "never"

try:
    import utils3d_moge as utils3d
except ImportError:  # pragma: no cover
    import utils3d

from fastapi import FastAPI, File, Form, UploadFile
from fastapi.responses import JSONResponse, Response
import uvicorn

from shared.protocol import (
    RESOLUTION_MAP, VALID_MODELS, MAX_INFER_DIM, EDGE_LTOL,
    NORMAL_EDGE_TOL_DEG, fov_y_from_fov_x, clamp_resolution,
)
from shared.floor import fit_floor_plane
from shared.tta import unflip_output, fuse_views, resize_grid
from shared.exif import fov_x_from_exif
from moge.model import import_model_class_by_version

app = FastAPI(title="MoDe Splat Daemon", version="2.1.0")
MAX_UPLOAD_SIZE = 64 * 1024 * 1024  # 64 MB cap to prevent memory exhaustion DoS


@app.middleware("http")
async def security_origin_check(request, call_next):
    """Block unauthorized cross-origin requests from external websites."""
    origin = request.headers.get("origin")
    if origin:
        allowed = ("http://127.0.0.1", "http://localhost", "https://127.0.0.1", "https://localhost")
        if not any(origin.startswith(prefix) for prefix in allowed):
            return JSONResponse(
                {"error": "Forbidden: cross-origin access from external websites is blocked."},
                status_code=403,
            )
    return await call_next(request)


MODELS: dict[str, torch.nn.Module] = {}
TIMINGS: dict[str, float] = {}

PRETRAINED = {
    ("v2", "vitl"): "Ruicheng/moge-2-vitl-normal",
    ("v3", "vitl"): "Ruicheng/moge-3-vitl",
    # Giant: measurably same quality on typical shots, 2.7x VRAM, 1.7x infer.
    # Kept as opt-in; loading it evicts vitl v3 (and vice versa) to fit 16GB.
    ("v3", "vitg"): "Ruicheng/moge-3-vitg",
}
VARIANTS = ("vitl", "vitg")


def _evict(key):
    m = MODELS.pop(key, None)
    if m is not None:
        try:
            del m
        except Exception:
            pass
        torch.cuda.empty_cache()
        print(f"[daemon] evicted {key} ({vram_mb():.0f}MB now)", flush=True)


def get_model(version: str, variant: str = "vitl"):
    key = (version, variant)
    if key not in MODELS:
        if key not in PRETRAINED:
            raise ValueError(f"Unknown model {version}/{variant}")
        # One v3 variant at a time: Giant (5GB weights, 7.3GB peak) + L do not
        # fit comfortably next to Blender on 16GB.
        if version == "v3":
            for other in list(MODELS):
                if other[0] == "v3" and other != key:
                    _evict(other)
        cls = import_model_class_by_version(version)
        print(f"[daemon] loading {version}/{variant} ({PRETRAINED[key]}) ...", flush=True)
        t0 = time.perf_counter()
        m = cls.from_pretrained(PRETRAINED[key]).cuda().eval()
        MODELS[key] = m
        dt = time.perf_counter() - t0
        print(f"[daemon] {version}/{variant} loaded in {dt:.1f}s ({vram_mb():.0f}MB)", flush=True)
    return MODELS[key]


def vram_mb() -> float:
    if torch.cuda.is_available():
        return torch.cuda.memory_allocated() / 1e6
    return 0.0


def run_infer(model, model_version: str, img_rgb: np.ndarray, level_int: int,
              refine_steps: int, fov_x=None) -> dict:
    """One MoGe forward pass for /infer. Returns numpy dict."""
    t = torch.tensor(np.ascontiguousarray(img_rgb), dtype=torch.float32,
                     device="cuda").permute(2, 0, 1) / 255.0
    kw: dict = {"apply_mask": False, "resolution_level": int(level_int), "use_fp16": True}
    if model_version == "v3":
        kw["refine_steps"] = int(refine_steps)
    if fov_x is not None:
        kw["fov_x"] = float(fov_x)
    try:
        with torch.no_grad():
            o = model.infer(t, **kw)
    except TypeError:
        kw.pop("fov_x", None)  # older checkpoints: estimate instead
        with torch.no_grad():
            o = model.infer(t, **kw)
    return {k: v.cpu().numpy() for k, v in o.items() if isinstance(v, torch.Tensor)}


def finalize_mask(points: np.ndarray, depth: np.ndarray, normal: np.ndarray,
                  mask, seamless: bool, apply_mask: bool, remove_edges: bool) -> np.ndarray:
    """Shared mask/edge policy for /infer and /pano faces."""
    finite = np.isfinite(depth) & np.all(np.isfinite(points), axis=-1)
    if seamless:
        return np.ascontiguousarray(finite.astype(bool))
    if apply_mask and mask is not None:
        mask_init = (np.asarray(mask) > 0.5) & finite
    else:
        mask_init = finite
    if not remove_edges:
        return np.ascontiguousarray(mask_init.astype(bool))
    try:
        d_edge = np.asarray(utils3d.np.depth_map_edge(depth, ltol=EDGE_LTOL)).astype(bool)
    except TypeError:
        d_edge = np.asarray(utils3d.np.depth_map_edge(depth)).astype(bool)
    n_edge = None
    try:
        if hasattr(utils3d.np, "normal_map_edge") and normal is not None and normal.shape[:2] == depth.shape:
            n_edge = np.asarray(
                utils3d.np.normal_map_edge(normal, tol=NORMAL_EDGE_TOL_DEG, mask=mask_init)
            ).astype(bool)
    except Exception:
        n_edge = None
    combined = (d_edge & n_edge) if n_edge is not None else d_edge
    # align shapes defensively
    if combined.shape != mask_init.shape:
        combined = np.zeros_like(mask_init, dtype=bool)
    return np.ascontiguousarray((mask_init & ~combined).astype(bool))


@app.get("/health")
def health():
    return {
        "status": "ok",
        "models_loaded": sorted(f"{v}/{u}" for v, u in MODELS.keys()),
        "vram_allocated_mb": round(vram_mb(), 1),
        "cuda": torch.cuda.is_available(),
        "cuda_name": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
    }


@app.post("/infer")
async def infer(
    image: UploadFile = File(...),
    model_version: str = Form("v3"),
    variant: str = Form("vitl"),
    resolution_level: str = Form("High"),
    refine_steps: int = Form(2),
    max_size: int = Form(1536),
    seamless: bool = Form(False),
    apply_mask: bool = Form(True),
    remove_edges: bool = Form(True),
    fov_x_override: Optional[float] = Form(None),
    tta: str = Form("off"),
):
    t_all = time.perf_counter()
    try:
        model_version = str(model_version).lower().strip()
        if model_version not in VALID_MODELS:
            return JSONResponse({"error": f"model_version must be one of {VALID_MODELS}"}, status_code=400)
        variant = str(variant).lower().strip() or "vitl"
        if variant not in VARIANTS:
            return JSONResponse({"error": f"variant must be one of {VARIANTS}"}, status_code=400)
        tta = str(tta).lower().strip() or "off"
        if tta not in ("off", "flip", "flip3"):
            return JSONResponse({"error": "tta must be off/flip/flip3"}, status_code=400)
        level_int = clamp_resolution(resolution_level) if not str(resolution_level).lstrip("-").isdigit() else clamp_resolution(int(resolution_level))
        max_size = max(512, min(int(max_size), MAX_INFER_DIM))
        refine_steps = max(0, min(int(refine_steps), 7))

        raw = await image.read()
        if not raw:
            return JSONResponse({"error": "empty image upload"}, status_code=400)
        if len(raw) > MAX_UPLOAD_SIZE:
            return JSONResponse(
                {"error": f"image payload exceeds {MAX_UPLOAD_SIZE // (1024 * 1024)}MB limit"},
                status_code=413,
            )
        arr = np.frombuffer(raw, dtype=np.uint8)
        bgr = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if bgr is None:
            return JSONResponse({"error": "could not decode image (use jpg/png/webp)"}, status_code=400)
        rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
        h0, w0 = rgb.shape[:2]
        if max(h0, w0) > max_size:
            s = max_size / max(h0, w0)
            rgb = cv2.resize(rgb, (0, 0), fx=s, fy=s, interpolation=cv2.INTER_AREA)
        h, w = rgb.shape[:2]

        # --- focal source: manual override > EXIF (free, phones) > model estimate.
        # Known focal goes INTO inference (all MoGe versions accept fov_x),
        # so geometry itself improves -- not just the reported number.
        fov_known = None
        fov_src = "model"
        if fov_x_override is not None and float(fov_x_override) > 1.0:
            fov_known = float(fov_x_override)
            fov_src = "manual"
        else:
            f_exif = fov_x_from_exif(raw)
            if f_exif is not None and 5.0 < f_exif < 160.0:
                fov_known = float(f_exif)
                fov_src = "exif"

        model = get_model(model_version, variant)

        def _run(img_rgb: np.ndarray):
            return run_infer(model, model_version, img_rgb, level_int, refine_steps,
                             fov_known)

        t_inf = time.perf_counter()
        out = _run(rgb)
        if tta == "flip":
            out_f = _run(np.ascontiguousarray(rgb[:, ::-1, :]))
            out = fuse_views([out, unflip_output(out_f)],
                             np.asarray(out["intrinsics"], dtype=np.float64))
        elif tta == "flip3":
            out_f = _run(np.ascontiguousarray(rgb[:, ::-1, :]))
            small = cv2.resize(rgb, (0, 0), fx=0.8, fy=0.8, interpolation=cv2.INTER_AREA)
            out_s = _run(small)
            hs, ws = out_s["depth"].shape
            hb, wb = out["depth"].shape
            for k in ("depth",):
                out_s[k] = resize_grid(np.asarray(out_s[k]), (hb, wb))
            if out_s.get("normal") is not None:
                n = resize_grid(np.asarray(out_s["normal"]), (hb, wb))
                out_s["normal"] = n / np.maximum(np.linalg.norm(n, axis=-1, keepdims=True), 1e-9)
            if out_s.get("mask") is not None:
                out_s["mask"] = resize_grid(np.asarray(out_s["mask"]), (hb, wb), is_mask=True) > 0.5
            if out_s.get("points") is not None:
                del out_s["points"]  # re-projected from fused depth below
            out = fuse_views([out, unflip_output(out_f), out_s],
                             np.asarray(out["intrinsics"], dtype=np.float64))
        t_inf = time.perf_counter() - t_inf

        points = out["points"]          # (H,W,3) OpenCV x-right y-down z-forward, metric for v2/v3
        depth = out["depth"]            # (H,W)
        intrinsics = np.asarray(out["intrinsics"], dtype=np.float32)  # normalized
        mask = out.get("mask", None)
        normal = out.get("normal", None)
        if normal is None:
            normal = np.zeros((*depth.shape, 3), dtype=np.float32)
        else:
            normal = np.asarray(normal, dtype=np.float32)

        # --- mask / edge handling (fixed: depth & normal combined) ---
        mask_final = finalize_mask(points, depth, normal, mask, seamless,
                                   apply_mask, remove_edges)

        # --- FOV (fixed conversion). fov_known already drove inference.
        fov_x, fov_y = utils3d.np.intrinsics_to_fov(intrinsics)
        fov_x, fov_y = float(np.rad2deg(fov_x)), float(np.rad2deg(fov_y))
        if fov_known is not None:
            fov_x = float(fov_known)
            fov_y = fov_y_from_fov_x(fov_x, w, h)

        buf = io.BytesIO()
        # uncompressed savez = fastest (~50ms for 2M pts), avoids zlib CPU spike
        np.savez(
            buf,
            points=np.ascontiguousarray(points.astype(np.float32)),
            depth=np.ascontiguousarray(depth.astype(np.float32)),
            normal=np.ascontiguousarray(normal.astype(np.float32)),
            mask=mask_final,
            intrinsics=np.ascontiguousarray(intrinsics.astype(np.float32)),
            image=np.ascontiguousarray(rgb),
            fov_x=np.float32(fov_x),
            fov_y=np.float32(fov_y),
            width=np.int32(w),
            height=np.int32(h),
            # decoupled-color support: let Blender sample the native file.
            # (older Blender clients ignore these keys.)
            orig_width=np.int32(w0),
            orig_height=np.int32(h0),
            tta=np.array(str(tta)),
            fov_src=np.array(str(fov_src)),
        )
        payload = buf.getvalue()
        dt = time.perf_counter() - t_all
        TIMINGS["last_total_s"] = dt
        TIMINGS["last_infer_s"] = t_inf
        print(
            f"[daemon] infer {w}x{h} {model_version}/{variant} L{level_int} r{refine_steps} "
            f"tta={tta} fov={fov_src} "
            f"infer={t_inf:.2f}s total={dt:.2f}s vram={vram_mb():.0f}MB pts={mask_final.sum()}",
            flush=True,
        )
        return Response(content=payload, media_type="application/x-numpy-archive")

    except Exception as e:  # never crash warm process on bad input
        traceback.print_exc()
        return JSONResponse({"error": f"{type(e).__name__}: {e}"}, status_code=500)


@app.post("/level")
async def level(
    maps: UploadFile = File(..., description=".npz from /infer (cached as response.npz)"),
    ransac_iters: int = Form(1500),
    cone_deg: float = Form(40.0),
    seed: int = Form(0),
):
    """Floor fit on cached infer maps. No GPU/model needed. Returns level matrix JSON."""
    t_all = time.perf_counter()
    try:
        raw = await maps.read()
        if len(raw) > MAX_UPLOAD_SIZE:
            return JSONResponse(
                {"error": f"maps payload exceeds {MAX_UPLOAD_SIZE // (1024 * 1024)}MB limit"},
                status_code=413,
            )
        try:
            z = np.load(io.BytesIO(raw), allow_pickle=False)
            points = np.asarray(z["points"], dtype=np.float64)
            normal = np.asarray(z["normal"], dtype=np.float64)
            mask = np.asarray(z["mask"]).astype(bool)
        except Exception as e:
            return JSONResponse({"error": f"bad .npz: {e}"}, status_code=400)
        if points.ndim != 3 or points.shape[-1] != 3 or normal.shape != points.shape:
            return JSONResponse({"error": "points/normal must be HxWx3 and match"}, status_code=400)
        if mask.shape != points.shape[:2]:
            return JSONResponse({"error": "mask must be HxW matching points"}, status_code=400)

        res = fit_floor_plane(
            points, normal, mask,
            ransac_iters=max(100, min(int(ransac_iters), 20000)),
            cone_deg=max(10.0, min(float(cone_deg), 90.0)),
            seed=int(seed),
        )
        res["elapsed_s"] = round(time.perf_counter() - t_all, 3)
        print(f"[daemon] level ok={res.get('ok')} {res.get('message','')[:90]} "
              f"({res['elapsed_s']}s)", flush=True)
        return JSONResponse(res)
    except Exception as e:  # never crash warm process on bad input
        traceback.print_exc()
        return JSONResponse({"error": f"{type(e).__name__}: {e}"}, status_code=500)


if __name__ == "__main__":
    # Warm default model so first Blender click is fast
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8766)
    ap.add_argument("--preload", default="v3", help="v3/v2/v3g/none")
    ap.add_argument("--variant", default="vitl", help="vitl/vitg (only for v3)")
    args = ap.parse_args()
    _pre = {"v3g": ("v3", "vitg")}.get(args.preload, (args.preload, args.variant))
    if _pre in PRETRAINED:
        try:
            get_model(*_pre)
        except Exception:
            traceback.print_exc()
            print("[daemon] preload failed, serving on-demand", flush=True)
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")
