"""Tests for verse + study_notes + cross-reference parsers.

Uses the real HTML fixture captured from wol.jw.org John 3 (nwtsty). The
fixture is checked into the repo so tests are deterministic and offline.
"""

from pathlib import Path

import pytest

from jw_core.parsers.study_notes import (
    parse_cross_references,
    parse_study_notes,
    study_notes_for_verse,
)
from jw_core.parsers.verse import get_verse, parse_verses

FIXTURE = Path(__file__).parent / "fixtures" / "nwtsty_john3.html"


@pytest.fixture(scope="module")
def john3_html() -> str:
    return FIXTURE.read_text(encoding="utf-8")


# ── Verses ──────────────────────────────────────────────────────────────

def test_parse_verses_count_matches_john3(john3_html: str) -> None:
    """John 3 has 36 verses."""
    verses = parse_verses(john3_html, book_num=43, chapter=3)
    assert len(verses) == 36


def test_parse_verses_strips_leading_number(john3_html: str) -> None:
    v1 = get_verse(john3_html, 43, 3, 1)
    assert v1 is not None
    assert not v1.text.startswith("3 ")  # leading verse number gone


def test_parse_verses_strips_pronunciation_marks(john3_html: str) -> None:
    v1 = get_verse(john3_html, 43, 3, 1)
    assert v1 is not None
    # "Nic·o·deʹmus" should become "Nicodemus" in the cleaned text.
    assert "Nicodemus" in v1.text
    assert "·" not in v1.text
    assert "ʹ" not in v1.text


def test_parse_verses_strips_inline_markers(john3_html: str) -> None:
    v1 = get_verse(john3_html, 43, 3, 1)
    assert v1 is not None
    # The original verse contains '+' markers; they should be gone.
    # Allow whitespace around but no bare '+' surrounded by letters.
    import re
    assert not re.search(r"\w\+\w", v1.text)


def test_parse_verses_returns_verse_3_16(john3_html: str) -> None:
    v = get_verse(john3_html, 43, 3, 16)
    assert v is not None
    # The most famous verse — text should mention "loved"
    assert "loved" in v.text.lower()


def test_verse_wol_url_uses_anchor(john3_html: str) -> None:
    v = get_verse(john3_html, 43, 3, 16)
    assert v is not None
    url = v.wol_url()
    assert "v=43:3:16" in url


def test_parse_verses_filters_by_book_chapter(john3_html: str) -> None:
    other = parse_verses(john3_html, book_num=99, chapter=3)
    assert other == []


# ── Study notes ─────────────────────────────────────────────────────────

def test_parse_study_notes_returns_many(john3_html: str) -> None:
    notes = parse_study_notes(john3_html, book_num=43, chapter=3)
    # John 3 has at least 15 study notes in nwtsty.
    assert len(notes) >= 15


def test_study_note_has_headword_and_body(john3_html: str) -> None:
    notes = parse_study_notes(john3_html, book_num=43, chapter=3)
    n0 = notes[0]
    assert n0.headword
    assert n0.body
    # Body should NOT begin with the headword (we strip it).
    assert not n0.body.lower().startswith(n0.headword.lower())


def test_study_note_associates_to_verse_for_known_headword(john3_html: str) -> None:
    notes = parse_study_notes(john3_html, book_num=43, chapter=3)
    # 'born again' should map to verse 3.
    matches = [n for n in notes if "born again" in n.headword.lower()]
    assert matches
    assert matches[0].verse == 3


def test_study_note_son_of_man_maps_to_verse_13(john3_html: str) -> None:
    notes = parse_study_notes(john3_html, book_num=43, chapter=3)
    matches = [n for n in notes if n.headword.lower() == "son of man"]
    assert matches
    assert matches[0].verse == 13


def test_study_note_pronunciation_marks_in_verse_match(john3_html: str) -> None:
    """'Nicodemus' headword should match verse 1 even though the verse
    originally contained 'Nic·o·deʹmus' — both get normalized to 'nicodemus'.
    """
    notes = parse_study_notes(john3_html, book_num=43, chapter=3)
    nicodemus = [n for n in notes if n.headword.lower() == "nicodemus"]
    assert nicodemus
    assert nicodemus[0].verse == 1


def test_study_note_inline_refs_captured(john3_html: str) -> None:
    notes = parse_study_notes(john3_html, book_num=43, chapter=3)
    notes_with_refs = [n for n in notes if n.inline_refs]
    assert notes_with_refs
    # First study note (Nicodemus) cites Joh 3:4, 9; 7:50; 19:39.
    nicodemus = next(n for n in notes if n.headword.lower() == "nicodemus")
    joined = " ".join(nicodemus.inline_refs)
    assert "3:4" in joined or "Joh 3:4" in joined


def test_study_notes_for_verse_helper(john3_html: str) -> None:
    notes = parse_study_notes(john3_html, book_num=43, chapter=3)
    v13_notes = study_notes_for_verse(notes, 13)
    assert v13_notes
    assert all(n.verse == 13 for n in v13_notes)


# ── Phase 3.5: 100% match rate on John 3 ───────────────────────────────

def test_phase35_all_notes_matched_by_headword(john3_html: str) -> None:
    """After the monotonic + multi-token upgrade, every note in John 3
    should be matched via headword tokens (no positional fallback needed)."""
    notes = parse_study_notes(john3_html, book_num=43, chapter=3)
    headword_matches = [n for n in notes if n.confidence == "headword"]
    assert len(headword_matches) == len(notes), (
        f"Expected 100% headword match; got {len(headword_matches)}/{len(notes)}"
    )


def test_phase35_verse_assignments_monotonic(john3_html: str) -> None:
    """Notes appear in verse order in the DOM and the parser preserves that."""
    notes = parse_study_notes(john3_html, book_num=43, chapter=3)
    verses = [n.verse for n in notes if n.verse is not None]
    assert verses == sorted(verses), "Note verse assignments must be monotonic"


def test_phase35_compound_headword_with_ellipsis(john3_html: str) -> None:
    """'wind … spirit' is the hard case: requires tokenization on punctuation
    rather than literal substring match."""
    notes = parse_study_notes(john3_html, book_num=43, chapter=3)
    wind = [n for n in notes if n.headword.lower().startswith("wind")]
    assert wind
    assert wind[0].verse == 8  # John 3:8 contains both 'wind' and 'spirit'


def test_phase35_positional_fallback_kept_as_safety_net() -> None:
    """If the headword genuinely has no matchable verse, the parser still
    returns the note with a positional estimate and confidence='positional'."""
    fake_html = """
    <html><body>
    <p data-pid="1">
      <span class="v" id="v43-3-1-1">1 alpha bravo charlie</span>
      <span class="v" id="v43-3-2-1">2 delta echo foxtrot</span>
    </p>
    <li class="item studyNote"><strong>nonexistent zebra:</strong> body</li>
    </body></html>
    """
    notes = parse_study_notes(fake_html, book_num=43, chapter=3)
    assert len(notes) == 1
    assert notes[0].verse is not None  # positional fallback fires
    assert notes[0].confidence == "positional"


def test_phase35_confidence_field_default() -> None:
    """Default confidence is 'headword' (the optimistic case)."""
    from jw_core.models import StudyNote
    n = StudyNote(book_num=43, chapter=3, headword="x", body="y")
    assert n.confidence == "headword"


# ── Cross-references ────────────────────────────────────────────────────

def test_parse_cross_references_returns_some(john3_html: str) -> None:
    refs = parse_cross_references(john3_html, book_num=43, chapter=3)
    # John 3 has many cross-references; at least dozens.
    assert len(refs) >= 10


def test_cross_reference_has_full_url(john3_html: str) -> None:
    refs = parse_cross_references(john3_html, book_num=43, chapter=3)
    r0 = refs[0]
    assert r0.href.startswith("/")
    assert r0.full_url().startswith("https://wol.jw.org")


def test_cross_reference_has_verse(john3_html: str) -> None:
    refs = parse_cross_references(john3_html, book_num=43, chapter=3)
    for r in refs:
        assert r.verse >= 1
        assert r.book_num == 43
        assert r.chapter == 3
