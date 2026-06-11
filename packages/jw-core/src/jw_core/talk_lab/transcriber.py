"""WhisperX-based transcriber with graceful fallback.

If WhisperX (F64) isn't available, returns an empty transcript so the
report still renders prosody-only counsel points.
"""

from __future__ import annotations

import logging

import numpy as np

from jw_core.talk_lab.models import TranscriptSegment, WordTiming

logger = logging.getLogger(__name__)


def transcribe(
    audio: np.ndarray, *, sr: int = 16000, language: str = "es"
) -> list[TranscriptSegment]:
    """Return word-level transcript. Empty list on failure or missing dep."""

    try:
        from jw_core.audio.asr_providers.whisperx import (  # type: ignore
            WhisperXProvider,
        )
    except Exception as exc:  # noqa: BLE001
        logger.info(
            "talk_lab: WhisperX not available (%s); using empty transcript",
            exc,
        )
        return []

    try:
        provider = WhisperXProvider(language=language)
        result = provider.transcribe(
            audio, sample_rate=sr, word_timestamps=True
        )
        segments: list[TranscriptSegment] = []
        for seg in result.segments:
            words = [
                WordTiming(
                    word=w.word,
                    start_s=w.start,
                    end_s=w.end,
                    confidence=w.confidence,
                )
                for w in (seg.words or [])
            ]
            segments.append(
                TranscriptSegment(
                    speaker=seg.speaker or "A",
                    text=seg.text,
                    start_s=seg.start,
                    end_s=seg.end,
                    words=words,
                )
            )
        return segments
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "talk_lab: WhisperX transcribe failed (%s); empty transcript",
            exc,
        )
        return []
