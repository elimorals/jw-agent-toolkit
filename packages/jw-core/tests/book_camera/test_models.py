"""Book-camera Pydantic models."""

from __future__ import annotations

import pytest

from jw_core.book_camera.models import (
    BibleVerseDetected,
    CameraFrameResult,
    OpenInWolAction,
    ReadAloudAction,
    StudyQuestionDetected,
)


def test_bible_verse_detected_required_fields() -> None:
    v = BibleVerseDetected(
        book_num=43,
        chapter=3,
        verse_start=16,
        wol_url="https://wol.jw.org/x",
    )
    assert v.kind == "bible_verse"
    assert v.verse_start == 16


def test_study_question_detected_defaults() -> None:
    q = StudyQuestionDetected(text="¿Qué es el reino?")
    assert q.kind == "study_question"
    assert q.suggested_topics == []


def test_camera_frame_result_round_trip() -> None:
    result = CameraFrameResult(
        captured_at="2026-06-11T15:00:00",
        ocr_text="Juan 3:16",
        ocr_confidence=0.92,
        detected=BibleVerseDetected(
            book_num=43, chapter=3, verse_start=16, wol_url="x"
        ),
        suggested_actions=[
            ReadAloudAction(text="Juan 3:16"),
            OpenInWolAction(url="https://wol.jw.org/x"),
        ],
    )
    dumped = result.model_dump()
    rehydrated = CameraFrameResult.model_validate(dumped)
    assert rehydrated.ocr_text == "Juan 3:16"
    assert rehydrated.detected.kind == "bible_verse"
    assert len(rehydrated.suggested_actions) == 2


def test_camera_frame_rejects_out_of_range_confidence() -> None:
    with pytest.raises(ValueError):
        CameraFrameResult(
            captured_at="now",
            ocr_text="x",
            ocr_confidence=1.5,
            detected=BibleVerseDetected(
                book_num=1, chapter=1, wol_url="x"
            ),
        )
