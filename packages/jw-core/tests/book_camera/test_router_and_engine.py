"""Action router + engine end-to-end tests (Fase 71)."""

from __future__ import annotations

import pytest

from jw_core.book_camera.engine import analyze_capture
from jw_core.book_camera.models import (
    BibleVerseDetected,
    PlainTextDetected,
    StudyQuestionDetected,
    WatchtowerParagraphDetected,
)
from jw_core.book_camera.router import suggested_actions_for


def test_router_for_bible_verse() -> None:
    detected = BibleVerseDetected(
        book_num=43,
        chapter=3,
        verse_start=16,
        wol_url="https://wol.jw.org/x",
    )
    actions = suggested_actions_for(detected, language="es")
    kinds = [a.kind for a in actions]
    assert kinds == ["read_aloud", "open_in_jw_library", "open_in_wol"]


def test_router_for_study_question() -> None:
    detected = StudyQuestionDetected(text="¿Qué es el reino?")
    actions = suggested_actions_for(detected, language="es")
    kinds = [a.kind for a in actions]
    assert kinds[0] == "show_answer"
    assert "read_aloud" in kinds


def test_router_for_watchtower_paragraph_includes_jw_library() -> None:
    detected = WatchtowerParagraphDetected(
        pub_code="w23.04",
        paragraph_id=5,
        text="...",
    )
    actions = suggested_actions_for(detected, language="es")
    assert any(a.kind == "open_in_jw_library" for a in actions)


def test_router_for_plain_text_only_read_aloud() -> None:
    actions = suggested_actions_for(
        PlainTextDetected(text="El amor es paciente."), language="es"
    )
    assert len(actions) == 1
    assert actions[0].kind == "read_aloud"


def test_engine_requires_image_or_text() -> None:
    with pytest.raises(ValueError):
        analyze_capture()


def test_engine_with_ocr_text_bible_verse() -> None:
    result = analyze_capture(ocr_text="Juan 3:16", language="es")
    assert result.detected.kind == "bible_verse"
    assert result.ocr_confidence > 0
    kinds = [a.kind for a in result.suggested_actions]
    assert "read_aloud" in kinds
    assert "open_in_wol" in kinds


def test_engine_with_ocr_text_study_question() -> None:
    result = analyze_capture(
        ocr_text="¿Qué es el reino de Dios?", language="es"
    )
    assert result.detected.kind == "study_question"
    assert result.suggested_actions[0].kind == "show_answer"


def test_engine_with_explicit_confidence() -> None:
    result = analyze_capture(
        ocr_text="Texto plano", ocr_confidence=0.55, language="es"
    )
    assert result.ocr_confidence == 0.55


def test_engine_with_empty_text_returns_unknown() -> None:
    result = analyze_capture(ocr_text="", language="es")
    assert result.detected.kind == "unknown"
    assert result.suggested_actions == []
