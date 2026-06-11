"""Content classifier tests (Fase 71)."""

from __future__ import annotations

from jw_core.book_camera.classifier import classify_content


def test_classify_bible_verse() -> None:
    out = classify_content("Juan 3:16")
    assert out.kind == "bible_verse"
    assert out.book_num == 43
    assert out.chapter == 3
    assert out.verse_start == 16
    assert out.wol_url.startswith("https://wol.jw.org")


def test_classify_bible_verse_english() -> None:
    out = classify_content("John 3:16")
    assert out.kind == "bible_verse"
    assert out.book_num == 43


def test_classify_watchtower_paragraph_with_code_and_paragraph() -> None:
    out = classify_content(
        "Como dice w23.04 página 12 párrafo 5, el reino..."
    )
    assert out.kind == "watchtower_paragraph"
    assert out.pub_code.lower().startswith("w23")
    assert out.paragraph_id == 5


def test_classify_watchtower_paragraph_code_only() -> None:
    out = classify_content("Información extra en g23 abril")
    assert out.kind == "watchtower_paragraph"
    assert out.paragraph_id is None


def test_classify_study_question() -> None:
    out = classify_content("¿Qué es el reino de Dios?")
    assert out.kind == "study_question"
    assert "reino" in out.text.lower()


def test_classify_plain_text() -> None:
    out = classify_content("El amor de Jehová es grande para todos.")
    assert out.kind == "plain_text"


def test_classify_unknown_on_noise() -> None:
    out = classify_content("!@!  ")
    assert out.kind == "unknown"


def test_classify_unknown_on_empty() -> None:
    out = classify_content("")
    assert out.kind == "unknown"


def test_classify_bible_ref_wins_over_question() -> None:
    """A line containing both a verse and a '?' classifies as bible_verse."""
    out = classify_content("¿Qué dice Juan 3:16?")
    assert out.kind == "bible_verse"


def test_classify_paragraph_wins_over_question() -> None:
    """Pub code wins over question heuristic."""
    out = classify_content("¿Recuerdas w23.04 párrafo 5?")
    assert out.kind == "watchtower_paragraph"
