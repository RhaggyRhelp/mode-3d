"""Scan-metadata summarizer. Pure stdlib (panel + tests share this)."""
from __future__ import annotations


def _fmt_m(v, digits=2):
    try:
        return f"{float(v):.{digits}f}m"
    except Exception:
        return "?"


def summarize(meta: dict) -> list:
    """meta.json dict -> [(icon, label, value)] rows for the viewer box."""
    if not isinstance(meta, dict) or not meta:
        return []
    rows = []
    if meta.get("kind") == "pano":
        rows.append(("FILE_IMAGE", "Room",
                     f"{meta.get('image_file', '?')} ({meta.get('faces', '?')} faces)"))
        model = f"{meta.get('model_version', '?')}/{meta.get('variant', 'vitl')}"
        rows.append(("PREFERENCES", "Model", model))
        rows.append(("CAMERA_DATA", "FOV", "90deg faces"))
        rows.append(("ORIENTATION_LOCAL", "Depth",
                     f"{_fmt_m(meta.get('min_depth'))} .. {_fmt_m(meta.get('max_depth'))}"))
        pts = meta.get("points", "?")
        try:
            pts = f"{int(pts):,}"
        except Exception:
            pass
        rows.append(("POINTCLOUD_DATA", "Splats", f"{pts} | {meta.get('radius_src', '?')}"))
        if meta.get("seam_resid") not in (None, "", "n/a"):
            rows.append(("VIEWZOOM", "Seam", str(meta["seam_resid"])))
        if meta.get("level"):
            rows.append(("SNAP_FACE", "Level", str(meta["level"])))
        return rows
    img = meta.get("image_file") or "scan"
    rows.append(("FILE_IMAGE", "Image",
                 f"{img} ({meta.get('orig_width', '?')}x{meta.get('orig_height', '?')} -> "
                 f"{meta.get('image_width', '?')}x{meta.get('image_height', '?')})"))
    model = f"{meta.get('model_version', '?')}/{meta.get('variant', 'vitl')}"
    if meta.get("tta") and meta["tta"] != "off":
        model += f" +TTA:{meta['tta']}"
    rows.append(("PREFERENCES", "Model", model))
    fov = f"{float(meta.get('fov_x', 0)):.1f}x{float(meta.get('fov_y', 0)):.1f}deg"
    if meta.get("fov_src"):
        fov += f" ({meta['fov_src']})"
    rows.append(("CAMERA_DATA", "FOV", fov))
    rows.append(("ORIENTATION_LOCAL", "Depth",
                 f"{_fmt_m(meta.get('min_depth'))} .. {_fmt_m(meta.get('max_depth'))}"))
    pts = meta.get("points", "?")
    try:
        pts = f"{int(pts):,}"
    except Exception:
        pass
    rows.append(("POINTCLOUD_DATA", "Splats", f"{pts} | {meta.get('color_src', '?')}"))
    rows.append(("DRIVER", "Radius", str(meta.get("radius_src", "?"))))
    if meta.get("zoom"):
        z = meta["zoom"]
        rows.append(("VIEWZOOM", "Zoom",
                     f"{z.get('points', '?')} pts, seam {z.get('seam_rel', '?')}"))
    if meta.get("level"):
        rows.append(("SNAP_FACE", "Level", str(meta["level"])))
    return rows
