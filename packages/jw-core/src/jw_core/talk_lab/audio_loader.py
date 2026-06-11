"""Audio loader: read WAV, resample to 16kHz mono, normalize to [-1, 1].

Uses scipy.signal.resample_poly when available (high quality) and falls
back to numpy linear interpolation otherwise. Only 16-bit PCM is
accepted to keep the dependency surface small.
"""

from __future__ import annotations

import logging
import wave
from pathlib import Path

import numpy as np

logger = logging.getLogger(__name__)


class AudioLoadError(RuntimeError):
    """Raised when the audio cannot be loaded."""


def load_audio_mono16k(path: str) -> tuple[np.ndarray, int]:
    """Load `path` as float32 mono at 16kHz, normalized to [-1, 1]."""

    p = Path(path)
    if not p.exists():
        raise AudioLoadError(f"not found: {p}")
    try:
        with wave.open(str(p), "rb") as w:
            n_channels = w.getnchannels()
            sample_width = w.getsampwidth()
            framerate = w.getframerate()
            n_frames = w.getnframes()
            raw = w.readframes(n_frames)
    except wave.Error as exc:
        raise AudioLoadError(f"wave.Error: {exc}") from exc

    if sample_width != 2:
        raise AudioLoadError(
            f"only 16-bit PCM supported (got {sample_width * 8}-bit)"
        )

    samples = np.frombuffer(raw, dtype=np.int16)
    if n_channels > 1:
        samples = (
            samples.reshape(-1, n_channels).mean(axis=1).astype(np.int16)
        )

    audio_f32 = samples.astype(np.float32) / 32768.0

    if framerate != 16000:
        try:
            from scipy.signal import resample_poly  # type: ignore

            audio_f32 = resample_poly(audio_f32, 16000, framerate).astype(
                np.float32
            )
        except ImportError:
            new_len = int(len(audio_f32) * 16000 / framerate)
            old_x = np.linspace(0, 1, len(audio_f32), endpoint=False)
            new_x = np.linspace(0, 1, new_len, endpoint=False)
            audio_f32 = np.interp(new_x, old_x, audio_f32).astype(np.float32)

    return audio_f32, 16000
