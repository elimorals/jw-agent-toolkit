"""Transcription via faster-whisper (optional, local).

VISION.md item: "Whisper local para dictar notas durante estudio personal".

This module is OPTIONAL — only loads `faster-whisper` if the user has
it installed (`pip install faster-whisper`). Otherwise `transcribe_file`
raises `TranscriptionError`.

We use `faster-whisper` (CTranslate2 backend) rather than `openai/whisper`
because it runs in <2× real-time on a Mac without GPU.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)


class TranscriptionError(RuntimeError):
    pass


@dataclass
class TranscriptionSegment:
    start: float
    end: float
    text: str


@dataclass
class TranscriptionResult:
    text: str
    language: str
    duration: float = 0.0
    segments: list[TranscriptionSegment] = field(default_factory=list)


def transcribe_file(
    audio_path: Path | str,
    *,
    model_size: str = "base",
    language: str | None = None,
    device: str = "auto",
    beam_size: int = 5,
) -> TranscriptionResult:
    """Run Whisper on `audio_path`.

    Args:
        audio_path: WAV/MP3/M4A/FLAC.
        model_size: 'tiny', 'base' (default), 'small', 'medium', 'large-v3'.
        language: optional ISO-639 hint; None = auto-detect.
        device: 'auto', 'cpu', or 'cuda'.
        beam_size: decoder beam size (higher = better, slower).
    """
    try:
        from faster_whisper import WhisperModel
    except ImportError as e:
        raise TranscriptionError("faster-whisper is not installed. `pip install faster-whisper`") from e

    model = WhisperModel(model_size, device=device, compute_type="int8")
    segments_iter, info = model.transcribe(
        str(audio_path),
        language=language,
        beam_size=beam_size,
    )

    segments: list[TranscriptionSegment] = []
    text_parts: list[str] = []
    for seg in segments_iter:
        segments.append(TranscriptionSegment(start=seg.start, end=seg.end, text=seg.text.strip()))
        text_parts.append(seg.text.strip())
    return TranscriptionResult(
        text=" ".join(text_parts),
        language=info.language,
        duration=info.duration,
        segments=segments,
    )


def estimate_real_time_factor(model_size: str) -> float:
    """Rough CPU-only Real-Time Factor (RTF) per model size on M2/M3.

    Lower is faster. Returned values are guidance, not guarantees.
    """
    return {
        "tiny": 0.1,
        "base": 0.2,
        "small": 0.4,
        "medium": 0.9,
        "large-v3": 2.0,
    }.get(model_size, 1.0)
