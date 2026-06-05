"""F64 — modelos para diarización extienden TranscriptionResult sin breaking."""

from __future__ import annotations

from jw_core.audio.transcription import (
    DiarizedResult,
    DiarizedSegment,
    TranscriptionResult,
    TranscriptionSegment,
)


def test_diarized_segment_is_subclass_of_transcription_segment() -> None:
    assert issubclass(DiarizedSegment, TranscriptionSegment)


def test_diarized_segment_has_speaker_id() -> None:
    seg = DiarizedSegment(start=0.0, end=1.5, text="Hola hermanos", speaker_id="SPEAKER_00")
    assert seg.speaker_id == "SPEAKER_00"
    assert seg.text == "Hola hermanos"


def test_diarized_segment_bible_refs_defaults_empty() -> None:
    seg = DiarizedSegment(start=0.0, end=1.5, text="hola")
    assert seg.bible_refs == ()


def test_diarized_result_extends_transcription_result() -> None:
    result = DiarizedResult(
        text="Hola hermanos. Génesis 1:1.",
        language="es",
        duration=3.0,
        segments=[
            DiarizedSegment(start=0.0, end=1.5, text="Hola hermanos.", speaker_id="SPEAKER_00"),
            DiarizedSegment(start=1.5, end=3.0, text="Génesis 1:1.", speaker_id="SPEAKER_00"),
        ],
        speaker_count=1,
    )
    assert isinstance(result, TranscriptionResult)
    assert result.speaker_count == 1
    assert len(result.segments) == 2
    assert all(isinstance(s, DiarizedSegment) for s in result.segments)
