"""Tests for the vision/multimodal module (Module 7)."""

from __future__ import annotations

import pytest
from jw_core.vision.maps import (
    BIBLICAL_JOURNEYS,
    get_journey,
    list_journeys,
    locations_near,
)
from jw_core.vision.ocr import OCRError, normalize_ocr_text
from jw_core.vision.slides import (
    SlideDeck,
    build_marp_deck,
    build_simple_deck,
    outline_to_deck,
)

# ── Maps ─────────────────────────────────────────────────────────────────


def test_journeys_loaded() -> None:
    keys = set(BIBLICAL_JOURNEYS.keys())
    assert {"paul_2nd", "paul_3rd", "exile_to_babylon"} <= keys


def test_journey_localized() -> None:
    j_en = get_journey("paul_2nd", language="en")
    j_es = get_journey("paul_2nd", language="es")
    assert j_en["title"] != j_es["title"]
    assert len(j_en["waypoints"]) == 6


def test_locations_near_jerusalem_includes_bethlehem() -> None:
    near = locations_near("jerusalem", radius_km=50, language="es")
    names = {n["canonical"] for n in near}
    assert "Bethlehem" in names


def test_locations_near_returns_empty_for_unknown() -> None:
    assert locations_near("atlantis") == []


def test_list_journeys_size() -> None:
    items = list_journeys("en")
    assert len(items) >= 3


# ── OCR ─────────────────────────────────────────────────────────────────


def test_normalize_collapses_whitespace() -> None:
    raw = "Hello    world\n\n\nfoo"
    assert normalize_ocr_text(raw) == "Hello world\nfoo"


def test_ocr_image_without_pytesseract_raises() -> None:
    # Try the OCR path: if pytesseract is installed, swallow the actual call;
    # otherwise verify we surface OCRError clearly.
    try:
        import pytesseract  # noqa: F401
    except ImportError:
        with pytest.raises(OCRError):
            from jw_core.vision.ocr import ocr_image

            ocr_image("nonexistent.png")


# ── Slides ──────────────────────────────────────────────────────────────


SAMPLE_OUTLINE = [
    {
        "heading": "Intro",
        "bullets": ["Theme: Hope of resurrection", "Open with Job 14:14"],
        "citation": "Job 14:14",
        "speaker_note": "Read with feeling.",
    },
    {
        "heading": "Main Point 1",
        "bullets": ["What is the resurrection?", "Why is it certain?"],
        "citation": "Acts 24:15",
    },
]


def test_simple_deck_separates_with_dashes() -> None:
    deck = outline_to_deck(title="T", subtitle="S", points=SAMPLE_OUTLINE)
    out = build_simple_deck(deck)
    assert "# T" in out
    assert "---" in out
    assert "Resurrection".lower() in out.lower()


def test_marp_deck_carries_directives_and_notes() -> None:
    deck = outline_to_deck(title="T", points=SAMPLE_OUTLINE, language="es", theme="gaia")
    out = build_marp_deck(deck)
    assert "marp: true" in out
    assert "theme: gaia" in out
    assert "lang: es" in out
    assert "<!-- speaker:" in out


def test_outline_to_deck_keeps_section_count() -> None:
    deck = outline_to_deck(title="t", points=SAMPLE_OUTLINE)
    assert isinstance(deck, SlideDeck)
    assert len(deck.sections) == 2
