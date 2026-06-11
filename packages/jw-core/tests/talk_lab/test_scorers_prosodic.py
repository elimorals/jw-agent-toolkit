"""Prosodic-only scorer tests."""

from __future__ import annotations

from typing import Any

from jw_core.talk_lab.models import (
    ProsodyFeatures,
    TranscriptSegment,
    WordTiming,
)
from jw_core.talk_lab.scorers.prosodic import (
    score_filler_use,
    score_pause_use,
    score_pronunciation,
    score_speech_rate,
)


def _features(**overrides: Any) -> ProsodyFeatures:
    base = {
        "duration_s": 60.0,
        "speech_rate_wpm": 130.0,
        "pitch_mean_hz": 180.0,
        "pitch_range_hz": 80.0,
        "intensity_mean_db": -20.0,
        "pause_count": 10,
        "pause_total_s": 10.0,
        "pause_avg_s": 1.0,
        "filler_count": 2,
        "filler_per_minute": 2.0,
    }
    base.update(overrides)
    return ProsodyFeatures(**base)


def _transcript_with_avg_confidence(c: float) -> list[TranscriptSegment]:
    words = [WordTiming(word="w", start_s=0, end_s=0.5, confidence=c)]
    return [
        TranscriptSegment(
            speaker="A", text="hi", start_s=0, end_s=1, words=words
        )
    ]


def test_pronunciation_high_confidence_score_3() -> None:
    transcript = _transcript_with_avg_confidence(0.92)
    r = score_pronunciation(_features(), transcript, language="en")
    assert r.score == 3


def test_pronunciation_low_confidence_score_0() -> None:
    transcript = _transcript_with_avg_confidence(0.45)
    r = score_pronunciation(_features(), transcript, language="en")
    assert r.score == 0


def test_pronunciation_no_transcript_score_0() -> None:
    r = score_pronunciation(_features(), [], language="en")
    assert r.score == 0
    assert "no word-level transcript" in r.evidence[0]


def test_speech_rate_ideal_3() -> None:
    r = score_speech_rate(_features(speech_rate_wpm=135.0), language="en")
    assert r.score == 3


def test_speech_rate_too_fast_0() -> None:
    r = score_speech_rate(_features(speech_rate_wpm=220.0), language="en")
    assert r.score == 0


def test_speech_rate_too_slow_1() -> None:
    r = score_speech_rate(_features(speech_rate_wpm=85.0), language="en")
    assert r.score == 1


def test_pause_use_ideal_3() -> None:
    r = score_pause_use(
        _features(pause_total_s=12.0, duration_s=60.0), language="en"
    )
    assert r.score == 3


def test_pause_use_zero_duration_score_0() -> None:
    r = score_pause_use(
        _features(duration_s=0.0, pause_total_s=0.0, speech_rate_wpm=0.0),
        language="en",
    )
    assert r.score == 0


def test_filler_use_low_score_3() -> None:
    r = score_filler_use(_features(filler_per_minute=1.5), language="en")
    assert r.score == 3


def test_filler_use_high_score_0() -> None:
    r = score_filler_use(_features(filler_per_minute=8.0), language="en")
    assert r.score == 0


def test_localized_title_es() -> None:
    r = score_speech_rate(_features(speech_rate_wpm=130.0), language="es")
    assert r.title_localized == "Velocidad del habla"
