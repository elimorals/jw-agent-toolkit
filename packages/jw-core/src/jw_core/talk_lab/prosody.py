"""Prosody feature extractor.

Uses librosa when available, falls back to numpy-only heuristics otherwise.
Returns a `ProsodyFeatures` Pydantic model.
"""

from __future__ import annotations

import logging

import numpy as np

from jw_core.talk_lab.models import ProsodyFeatures

logger = logging.getLogger(__name__)

_PAUSE_RMS_THRESHOLD = 0.005
_PAUSE_FRAME_MS = 25
_PAUSE_MIN_DURATION_S = 0.30


def _frame_rms(audio: np.ndarray, frame_size: int) -> np.ndarray:
    n_frames = len(audio) // frame_size
    if n_frames == 0:
        return np.array([], dtype=np.float32)
    trimmed = audio[: n_frames * frame_size].reshape(n_frames, frame_size)
    return np.sqrt(
        np.mean(trimmed.astype(np.float64) ** 2, axis=1)
    ).astype(np.float32)


def _detect_pauses(
    rms: np.ndarray, sr: int, frame_size: int
) -> tuple[int, float, float]:
    if rms.size == 0:
        return (0, 0.0, 0.0)
    silence_mask = rms < _PAUSE_RMS_THRESHOLD
    if not silence_mask.any():
        return (0, 0.0, 0.0)
    frame_dur = frame_size / sr
    pauses: list[float] = []
    current = 0
    for is_sil in silence_mask:
        if is_sil:
            current += 1
        else:
            if current * frame_dur >= _PAUSE_MIN_DURATION_S:
                pauses.append(current * frame_dur)
            current = 0
    if current * frame_dur >= _PAUSE_MIN_DURATION_S:
        pauses.append(current * frame_dur)
    return (
        len(pauses),
        float(sum(pauses)),
        float(np.mean(pauses)) if pauses else 0.0,
    )


def _estimate_pitch(audio: np.ndarray, sr: int) -> tuple[float, float]:
    """Crude pitch tracker.

    Uses librosa.yin when available. Otherwise approximates pitch via
    zero-crossing rate on energy-bearing windows. Returns (mean_hz,
    range_hz) clamped to the human voice range, or (0.0, 0.0) when no
    voiced frames are found.
    """

    try:
        import librosa  # type: ignore

        f0 = librosa.yin(audio, fmin=80.0, fmax=400.0, sr=sr)
        voiced = f0[np.isfinite(f0) & (f0 > 0)]
        if voiced.size == 0:
            return (0.0, 0.0)
        mean = float(np.mean(voiced))
        rng = float(
            np.percentile(voiced, 95) - np.percentile(voiced, 5)
        )
        return (mean, rng)
    except Exception:
        if audio.size < sr * 0.05:
            return (0.0, 0.0)
        window = 1024
        crossings_per_frame: list[int] = []
        for i in range(0, len(audio) - window, window):
            seg = audio[i : i + window]
            crossings = int(np.sum(np.diff(np.sign(seg)) != 0))
            crossings_per_frame.append(crossings)
        if not crossings_per_frame:
            return (0.0, 0.0)
        rate = float(np.mean(crossings_per_frame)) * (sr / window) / 2.0
        if rate < 60 or rate > 500:
            return (0.0, 0.0)
        return (rate, max(rate * 0.4, 0.0))


def extract_prosody(
    audio: np.ndarray,
    *,
    sr: int = 16000,
    word_count: int,
    filler_count: int = 0,
) -> ProsodyFeatures:
    """Extract a `ProsodyFeatures` from an audio array."""

    duration_s = float(len(audio) / sr)
    frame_size = int(sr * _PAUSE_FRAME_MS / 1000)
    rms = _frame_rms(audio, frame_size)
    if audio.size:
        rms_total = float(
            np.sqrt(np.mean(audio.astype(np.float64) ** 2) + 1e-12)
        )
        intensity_db = 20.0 * float(np.log10(max(rms_total, 1e-6)))
    else:
        intensity_db = -120.0

    pause_count, pause_total, pause_avg = _detect_pauses(
        rms, sr, frame_size
    )

    speech_rate_wpm = (
        (word_count / duration_s) * 60.0 if duration_s > 0 else 0.0
    )
    pitch_mean, pitch_range = _estimate_pitch(audio, sr)
    filler_per_minute = (
        (filler_count / duration_s) * 60.0 if duration_s > 0 else 0.0
    )

    return ProsodyFeatures(
        duration_s=duration_s,
        speech_rate_wpm=speech_rate_wpm,
        pitch_mean_hz=pitch_mean,
        pitch_range_hz=pitch_range,
        intensity_mean_db=intensity_db,
        pause_count=pause_count,
        pause_total_s=pause_total,
        pause_avg_s=pause_avg,
        filler_count=filler_count,
        filler_per_minute=filler_per_minute,
    )
