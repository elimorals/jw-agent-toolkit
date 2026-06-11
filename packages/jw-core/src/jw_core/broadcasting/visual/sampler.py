"""Frame sampler for visual broadcasting indexing (Fase 69).

Streams frames at fixed intervals using `ffmpeg`. Returns each frame
as `(timestamp_s, image_bytes)` where `image_bytes` is JPEG-encoded
raw bytes. The frames are NEVER written to disk by this layer; the
caller decides whether to thumbnail.

`ffmpeg` is import-guarded: if the binary is not in PATH, an explicit
`FrameSamplerError` surfaces with installation guidance. Tests use
`fake_sample()` to bypass ffmpeg entirely.
"""

from __future__ import annotations

import logging
import shutil
import subprocess
from collections.abc import Iterator
from pathlib import Path

logger = logging.getLogger(__name__)


class FrameSamplerError(RuntimeError):
    """Raised when the sampler cannot proceed."""


def ffmpeg_available() -> bool:
    """True if `ffmpeg` is on PATH."""
    return shutil.which("ffmpeg") is not None


def sample_frames(
    video_path: str | Path,
    *,
    interval_s: float = 5.0,
    max_frames: int | None = None,
) -> Iterator[tuple[float, bytes]]:
    """Yield `(timestamp_s, jpeg_bytes)` every `interval_s` seconds.

    Uses `ffmpeg -vf fps=1/interval` to write JPEGs to stdout via image2
    pipe. Each output frame is parsed by SOI/EOI markers.
    """

    if not ffmpeg_available():
        raise FrameSamplerError(
            "ffmpeg not found on PATH. Install: `brew install ffmpeg` or "
            "`apt install ffmpeg`."
        )
    p = Path(video_path)
    if not p.exists():
        raise FrameSamplerError(f"video not found: {p}")

    fps = 1.0 / max(interval_s, 0.01)
    cmd = [
        "ffmpeg",
        "-i",
        str(p),
        "-vf",
        f"fps={fps}",
        "-f",
        "image2pipe",
        "-vcodec",
        "mjpeg",
        "-q:v",
        "5",
        "-",
    ]
    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
    except Exception as exc:
        raise FrameSamplerError(f"failed to spawn ffmpeg: {exc}") from exc
    if proc.stdout is None:
        raise FrameSamplerError("ffmpeg stdout pipe unavailable")

    buf = b""
    yielded = 0
    soi = b"\xff\xd8"
    eoi = b"\xff\xd9"
    while True:
        chunk = proc.stdout.read(4096)
        if not chunk:
            break
        buf += chunk
        while True:
            start = buf.find(soi)
            if start < 0:
                break
            end = buf.find(eoi, start + 2)
            if end < 0:
                break
            jpeg = buf[start : end + 2]
            buf = buf[end + 2 :]
            ts = yielded * interval_s
            yield (ts, jpeg)
            yielded += 1
            if max_frames is not None and yielded >= max_frames:
                proc.terminate()
                return
    proc.wait()


def fake_sample(
    *,
    duration_s: float = 30.0,
    interval_s: float = 5.0,
) -> Iterator[tuple[float, bytes]]:
    """Yield deterministic fake `(timestamp_s, image_bytes)` for tests.

    `image_bytes` is just `b"fake-frame-<ts>"` so providers can hash it
    into a stable caption / embedding.
    """
    ts = 0.0
    while ts <= duration_s:
        yield (ts, f"fake-frame-{ts}".encode())
        ts += interval_s
