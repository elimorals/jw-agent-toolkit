"""Image preprocessing for the quote verifier (Fase 70).

Loads an image via PIL, honors EXIF orientation, computes a perceptual
hash (pHash) for fuzzy duplicate detection, and reports format + size.
The preprocessor never modifies the file on disk.
"""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class ImagePreprocessError(RuntimeError):
    """Raised when the image cannot be loaded or preprocessed."""


def _phash_simple(image: Any) -> str:
    """Cheap perceptual-ish hash: downsample to 8x8 grayscale, threshold,
    pack into hex.

    This is NOT a real DCT-based pHash but is robust to JPEG re-encoding
    at the same dimensions and is enough to ground tests + a basic
    dedup signal. Real `imagehash` library can be plugged in later.
    """
    try:
        from PIL import Image  # type: ignore

        gray = image.convert("L").resize((8, 8), Image.NEAREST)
        pixels = list(gray.getdata())
    except Exception as exc:
        raise ImagePreprocessError(f"phash failed: {exc}") from exc
    mean = sum(pixels) / len(pixels)
    bits = "".join("1" if p >= mean else "0" for p in pixels)
    return hex(int(bits, 2))[2:].rjust(16, "0")


def load_image(path: str | Path) -> tuple[Any, dict]:
    """Load an image and return `(PIL.Image, metadata_dict)`.

    Metadata includes: `phash`, `format`, `size` (w, h).
    """
    p = Path(path)
    if not p.exists():
        raise ImagePreprocessError(f"not found: {p}")
    try:
        from PIL import ExifTags, Image  # type: ignore
    except ImportError as exc:
        raise ImagePreprocessError(
            "Pillow not installed. Install with: pip install Pillow"
        ) from exc
    try:
        img = Image.open(p)
        img.load()
    except Exception as exc:
        raise ImagePreprocessError(f"PIL.open failed: {exc}") from exc

    # Honor EXIF orientation when present (defensive: skip on missing exif)
    try:
        orientation_tag = next(
            (k for k, v in ExifTags.TAGS.items() if v == "Orientation"),
            None,
        )
        exif = img.getexif() if hasattr(img, "getexif") else None
        if exif and orientation_tag and orientation_tag in exif:
            o = exif[orientation_tag]
            if o == 3:
                img = img.rotate(180, expand=True)
            elif o == 6:
                img = img.rotate(270, expand=True)
            elif o == 8:
                img = img.rotate(90, expand=True)
    except Exception:
        pass

    fmt = img.format or ""
    size = img.size
    try:
        phash = _phash_simple(img)
    except ImagePreprocessError:
        phash = hashlib.sha256(p.read_bytes()).hexdigest()[:16]

    return (img, {"phash": phash, "format": fmt, "size": size})
