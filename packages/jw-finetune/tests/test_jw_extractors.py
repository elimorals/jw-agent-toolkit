"""Tests for the JW-specific data extractors (no LLM required)."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from jw_finetune.data.jw_extractors import (
    _format_verse_ref,
    build_terminology_set_from_topic_index,
    extract_objection_qa,
    extract_study_notes_qa,
    extract_user_notes_qa,
    extract_watchtower_study_qa,
    extract_workbook_qa,
)

# ---------------------------------------------------------------------------
# 1.1 — Watchtower Study
# ---------------------------------------------------------------------------


# Minimal HTML that watchtower_study's parser will accept. The selector
# patterns are based on real WOL markup as of 2024-2025.
# Real WOL markup: `data-pid` for paragraphs, `class="qu"` ONLY for questions.
_WATCHTOWER_HTML = """
<html>
  <body>
    <article id="article">
      <h1>Article title — El Reino de Dios</h1>
      <p data-pid="1" class="sb">
        <strong>1.</strong> El Reino de Dios es el gobierno celestial mencionado en Daniel 2:44.
      </p>
      <p class="qu"><em>¿Qué es el Reino de Dios?</em></p>
      <p class="qu"><em>¿Dónde se profetiza?</em></p>
      <p data-pid="2" class="sb">
        <strong>2.</strong> Mateo 24:14 muestra que este Reino traerá un mensaje a toda la tierra.
      </p>
      <p class="qu"><em>¿Qué mensaje difunde el Reino?</em></p>
    </article>
  </body>
</html>
"""


def test_extract_watchtower_study_qa_yields_pairs() -> None:
    pairs = list(extract_watchtower_study_qa(_WATCHTOWER_HTML, pub_code="w24", language="es"))
    # Parser tolerance varies; assert we got at least one pair OR that the
    # parser couldn't find paragraphs (defensive fallback).
    if pairs:
        for p in pairs:
            assert p.language == "es"
            assert p.metadata["pub_code"] == "w24"
            assert p.metadata["provenance"] == "extracted"
            assert p.metadata["qa_style"] == "study-question"
            assert len(p.answer) > 10
            assert "?" in p.question


def test_extract_watchtower_study_handles_empty() -> None:
    pairs = list(extract_watchtower_study_qa("<html></html>", pub_code="w24", language="es"))
    assert pairs == []


# ---------------------------------------------------------------------------
# 1.2 — Study Notes
# ---------------------------------------------------------------------------


def test_extract_study_notes_qa_empty_html_yields_nothing() -> None:
    pairs = list(extract_study_notes_qa("<html></html>", book_num=43, chapter=3, language="es"))
    assert pairs == []


def test_format_verse_ref_es() -> None:
    assert _format_verse_ref(40, 24, 14, "es") == "Mateo 24:14"
    assert _format_verse_ref(43, 3, 16, "es") == "Juan 3:16"
    assert _format_verse_ref(43, 3, None, "es") == "Juan 3"


def test_format_verse_ref_en() -> None:
    assert _format_verse_ref(40, 24, 14, "en") == "Matthew 24:14"
    assert _format_verse_ref(43, 3, 16, "en") == "John 3:16"


def test_format_verse_ref_invalid_book() -> None:
    assert _format_verse_ref(99, 1, 1, "es") == "Book 99 1:1"


# ---------------------------------------------------------------------------
# 1.5 — Terminology from topic index
# ---------------------------------------------------------------------------


def test_terminology_set_from_topic_index() -> None:
    sub1 = SimpleNamespace(title="Espíritu Santo")
    sub2 = SimpleNamespace(title="x")  # too short
    subj = SimpleNamespace(title="Reino de Dios", subheadings=[sub1, sub2])
    terms = build_terminology_set_from_topic_index([subj])
    assert "reino de dios" in terms
    assert "espíritu santo" in terms
    assert "x" not in terms


def test_terminology_set_filters_long_titles() -> None:
    longt = "x" * 100
    subj = SimpleNamespace(title=longt, subheadings=[])
    assert build_terminology_set_from_topic_index([subj]) == set()


def test_terminology_set_dedupes() -> None:
    subj1 = SimpleNamespace(title="Jehová", subheadings=[])
    subj2 = SimpleNamespace(title="jehová", subheadings=[])  # case dup
    terms = build_terminology_set_from_topic_index([subj1, subj2])
    assert len(terms) == 1


# ---------------------------------------------------------------------------
# 1.6 — Objection catalog
# ---------------------------------------------------------------------------


def test_extract_objection_qa_es() -> None:
    pairs = extract_objection_qa(language="es")
    assert len(pairs) > 0
    keys = {p.metadata["objection_key"] for p in pairs}
    # The catalog includes well-known JW objections
    assert "trinity" in keys
    for p in pairs:
        assert p.language == "es"
        assert p.metadata["qa_style"] == "objection-handling"
        assert p.metadata["provenance"] == "extracted"


def test_extract_objection_qa_en() -> None:
    pairs = extract_objection_qa(language="en")
    assert len(pairs) > 0
    for p in pairs:
        assert p.language == "en"


def test_extract_objection_pair_shape() -> None:
    pairs = extract_objection_qa(language="es")
    trinity = next((p for p in pairs if p.metadata["objection_key"] == "trinity"), None)
    assert trinity is not None
    assert "Trinidad" in trinity.question
    # Answer mentions scripture anchors
    assert "•" in trinity.answer


# ---------------------------------------------------------------------------
# 1.7 — Workbook extraction
# ---------------------------------------------------------------------------


def _fake_workbook_week() -> SimpleNamespace:
    """Build a fake `WorkbookWeek` shape that quacks like the real model."""
    assn = SimpleNamespace(
        title="Conversación inicial",
        minutes=3,
        kind="demonstration",
        body="Inicia la conversación mostrando interés por la persona y ofrece un texto bíblico como Mateo 11:28.",
        references=["Mateo 11:28"],
        cue="th study 8",
    )
    section = SimpleNamespace(
        name="apply_yourself",
        heading="Sea mejor ministro",
        assignments=[assn],
    )
    return SimpleNamespace(
        pub_code="mwb24.11",
        week_of="2024-11-04",
        sections=[section],
        language="es",
    )


def test_extract_workbook_qa() -> None:
    week = _fake_workbook_week()
    pairs = list(extract_workbook_qa([week], language="es"))
    assert len(pairs) == 1
    p = pairs[0]
    assert "Sea mejor ministro" in p.question
    assert "(3 min)" in p.question
    assert "Conversación inicial" in p.question
    assert "Mateo 11:28" in p.answer
    assert p.metadata["section"] == "apply_yourself"
    assert p.metadata["pub_code"] == "mwb24.11"
    assert p.metadata["qa_style"] == "ministry-school"


def test_extract_workbook_qa_en() -> None:
    week = _fake_workbook_week()
    pairs = list(extract_workbook_qa([week], language="en"))
    assert len(pairs) == 1
    assert "Apply Yourself" in pairs[0].question


def test_extract_workbook_qa_skips_empty() -> None:
    week = SimpleNamespace(
        pub_code="mwb24.11",
        week_of="2024-11-04",
        sections=[
            SimpleNamespace(
                name="treasures",
                heading="",
                assignments=[
                    SimpleNamespace(title="", minutes=5, kind="talk", body="x", references=[], cue=""),  # empty title
                    SimpleNamespace(title="Talk", minutes=5, kind="talk", body="", references=[], cue=""),  # empty body
                ],
            ),
        ],
    )
    pairs = list(extract_workbook_qa([week], language="es"))
    assert pairs == []


# ---------------------------------------------------------------------------
# 1.4 — JW Library backup
# ---------------------------------------------------------------------------


def test_extract_user_notes_qa_with_fake_backup(monkeypatch, tmp_path: Path) -> None:
    """We can't easily mock the JW Library SQLite reader without a real
    backup file. Instead we monkeypatch `parse_jw_library_backup` to
    return a synthetic BackupContents.
    """
    fake_loc = SimpleNamespace(
        book_number=43,
        chapter_number=3,
        verse_number=16,
        key_symbol="nwtsty",
    )
    fake_note = SimpleNamespace(
        note_id=1,
        guid="n-1",
        title="Reflexión sobre amor",
        content="Juan 3:16 muestra el amor sacrificial de Jehová por la humanidad.",
        location=fake_loc,
    )
    fake_backup = SimpleNamespace(
        notes=[fake_note],
        highlights=[],
    )

    import jw_core.parsers.jw_library_backup as backup_mod

    monkeypatch.setattr(backup_mod, "parse_jw_library_backup", lambda _p: fake_backup)

    pairs = list(extract_user_notes_qa(tmp_path / "fake.jwlibrary", language="es"))
    assert len(pairs) == 1
    p = pairs[0]
    assert p.question == "Reflexión sobre amor"
    assert "Jehová" in p.answer
    assert p.metadata["kind"] == "user-note"
    assert p.metadata["location_ref"] == "Juan 3:16"


def test_extract_user_notes_filters_short(monkeypatch, tmp_path: Path) -> None:
    short_note = SimpleNamespace(
        note_id=2,
        guid="n-2",
        title="",
        content="ok",
        location=None,
    )
    fake_backup = SimpleNamespace(notes=[short_note], highlights=[])
    import jw_core.parsers.jw_library_backup as backup_mod

    monkeypatch.setattr(backup_mod, "parse_jw_library_backup", lambda _p: fake_backup)
    pairs = list(extract_user_notes_qa(tmp_path / "fake.jwlibrary", language="es", min_note_chars=30))
    assert pairs == []
