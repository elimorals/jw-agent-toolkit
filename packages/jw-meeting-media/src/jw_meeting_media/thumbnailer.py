"""Genera thumbnails para imagen (Pillow) y video (ffmpeg subprocess).

Cache idempotente por sha256(input_path)+max_size.
"""

from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path


class Thumbnailer:
    def __init__(self, *, cache_root: Path):
        self._cache_root = Path(cache_root)
        self._cache_root.mkdir(parents=True, exist_ok=True)

    def for_image(self, source: Path, *, max_size: int = 200) -> Path:
        from PIL import Image

        key = self._cache_key(source, max_size)
        target = self._cache_root / f"{key}.jpg"
        if target.exists():
            return target
        with Image.open(source) as img:
            img.thumbnail((max_size, max_size))
            if img.mode != "RGB":
                img = img.convert("RGB")
            img.save(target, "JPEG", quality=85)
        return target

    def for_video(
        self,
        source: Path,
        *,
        max_size: int = 200,
        at_seconds: float = 1.0,
    ) -> Path:
        key = self._cache_key(source, max_size, suffix=f"@{at_seconds}")
        target = self._cache_root / f"{key}.jpg"
        if target.exists():
            return target
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-i",
                str(source),
                "-ss",
                str(at_seconds),
                "-vframes",
                "1",
                "-vf",
                f"scale={max_size}:-1",
                str(target),
            ],
            check=True,
            stderr=subprocess.DEVNULL,
        )
        return target

    def _cache_key(self, source: Path, max_size: int, suffix: str = "") -> str:
        with source.open("rb") as f:
            h = hashlib.sha256(f.read(65536)).hexdigest()[:16]
        return f"{h}_{max_size}{suffix}"
