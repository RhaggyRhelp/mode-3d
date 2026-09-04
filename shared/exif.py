"""EXIF focal length -> horizontal FOV. PIL only (stdlib + pillow)."""
from __future__ import annotations

import io
import math

# EXIF tag: FocalLengthIn35mmFilm (SHORT). Phones (Pixel/iPhone) write it.
TAG_F35 = 41989


def _tag_35mm(exif) -> object:
    v = exif.get(TAG_F35)
    if v not in (None, 0):
        return v
    try:  # nested EXIF IFD (where phones actually write it)
        sub = exif.get_ifd(0x8769)
        v = sub.get(TAG_F35)
        if v not in (None, 0):
            return v
    except Exception:
        pass
    return None


def fov_x_from_exif(img_bytes: bytes):
    """Return HFOV degrees from 35mm-equivalent focal, or None if absent/invalid."""
    try:
        from PIL import Image as PILImage
        with PILImage.open(io.BytesIO(img_bytes)) as im:
            exif = im.getexif()
            if not exif:
                return None
            f35 = _tag_35mm(exif)
        if f35 in (None, 0):
            return None
        f35 = float(f35)
        if not 5.0 < f35 < 500.0:
            return None
        # 36mm-wide full frame, half-width 18mm
        return math.degrees(2.0 * math.atan(18.0 / f35))
    except Exception:
        return None
