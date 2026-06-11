"""Linguistic scorer tests."""

from __future__ import annotations

from jw_core.talk_lab.models import TranscriptSegment
from jw_core.talk_lab.scorers.linguistic import score_scripture_use


def _ts(text: str) -> list[TranscriptSegment]:
    return [TranscriptSegment(speaker="A", text=text, start_s=0, end_s=1)]


def test_scripture_use_high_with_explicit_reference() -> None:
    transcript = _ts("As John 3:16 makes clear, this principle...")
    r = score_scripture_use(transcript, language="en")
    assert r.score >= 1


def test_scripture_use_low_without_any_ref() -> None:
    transcript = _ts("Just talk no scriptures here at all.")
    r = score_scripture_use(transcript, language="en")
    assert r.score == 0


def test_scripture_use_three_refs_score_3() -> None:
    transcript = _ts("John 3:16, Matthew 24:14, and Romans 12:1 are key.")
    r = score_scripture_use(transcript, language="en")
    assert r.score == 3


def test_localized_title_es() -> None:
    transcript = _ts("ningún versículo")
    r = score_scripture_use(transcript, language="es")
    assert r.title_localized == "Uso de la Escritura"
