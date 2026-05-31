"""Hardware detection helpers for the audio stack.

Pure stdlib; no torch/onnx import at module level.
"""

from __future__ import annotations

import platform
import shutil
import sys
from typing import Literal

Target = Literal["api", "nvidia", "mlx", "cpu"]


def detect_target() -> Target:
    """Detect the strongest local accelerator. API is opt-in only."""

    if shutil.which("nvidia-smi"):
        return "nvidia"
    if sys.platform == "darwin" and platform.machine() == "arm64":
        return "mlx"
    return "cpu"


def available_vram_gb() -> float:
    """Best-effort VRAM detection. Returns 0.0 if unknown.

    - CUDA: torch.cuda.mem_get_info()[1] / 1024**3 if torch installed.
    - MPS: psutil.virtual_memory().available / 1024**3 (approximation,
      shared system memory).
    - else: 0.0
    """

    try:
        import torch  # type: ignore[import-not-found]

        if torch.cuda.is_available():
            free, _total = torch.cuda.mem_get_info()
            return float(free) / (1024**3)
    except Exception:
        pass

    if sys.platform == "darwin" and platform.machine() == "arm64":
        try:
            import psutil  # type: ignore[import-not-found]

            return float(psutil.virtual_memory().available) / (1024**3)
        except Exception:
            return 0.0
    return 0.0


WHISPER_CHAIN: list[tuple[float, str]] = [
    (8.0, "large-v3-turbo"),
    (4.0, "medium"),
    (2.0, "small"),
    (1.0, "base"),
    (0.0, "tiny"),
]


def recommend_model_size() -> str:
    """Pick a Whisper model size based on available VRAM/RAM.

    Strict greater-than: a value sitting *exactly* on a tier boundary falls to
    the next size down. This keeps tests deterministic and leaves a small
    safety margin for fluctuating free-memory readings.
    """

    vram = available_vram_gb()
    for threshold, name in WHISPER_CHAIN:
        if vram > threshold:
            return name
    return "tiny"
