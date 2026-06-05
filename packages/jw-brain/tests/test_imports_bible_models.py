"""Modelos intermediarios del bible KG. No persistencia — son la frontera
entre parser y loader."""

from __future__ import annotations

import pytest
from jw_brain.imports.bible.models import (
    BibleKgPassage,
    BibleKgPeriod,
    BibleKgPerson,
    BibleKgPlace,
    InsightEntry,
)
from pydantic import ValidationError


def test_insight_entry_minimal():
    entry = InsightEntry(
        headword="Abraham",
        document_id=1234,
        symbol="it-1",
        meps_language=0,  # English
        kind="person",
        first_mention_raw="Gen. 11:26",
        first_mention_href="/en/wol/d/r1/lp-e/1001070026",
        aliases=("Abram",),
        text_excerpt="Abraham, son of Terah...",
    )
    assert entry.kind == "person"
    assert entry.aliases == ("Abram",)


def test_bible_kg_person_canonical_id():
    p = BibleKgPerson(
        slug="abraham",
        name="Abraham",
        aliases=("Abram",),
        era="patriarchal",
        first_mention_book=1,
        first_mention_chapter=11,
        first_mention_verse=26,
        description_excerpt="Son of Terah...",
        source_url="https://wol.jw.org/en/wol/d/r1/lp-e/1200000124",
    )
    assert p.canonical_id == "person:abraham"


def test_bible_kg_place_canonical_id():
    pl = BibleKgPlace(
        slug="jerusalem",
        name="Jerusalem",
        region="Judea",
        modern_name="Jerusalem (modern)",
        latitude=31.7857,
        longitude=35.2278,
        eras_active=("united_kingdom", "divided_kingdom", "babylonian_exile"),
        source_url="https://wol.jw.org/en/wol/d/r1/lp-e/1200001234",
    )
    assert pl.canonical_id == "place:jerusalem"


def test_bible_kg_period_canonical_id():
    period = BibleKgPeriod(
        slug="patriarchal",
        name="Era Patriarcal",
        start_year_bce=2018,
        end_year_bce=1657,
        description="Desde el llamamiento de Abraham hasta el establecimiento en Egipto.",
    )
    assert period.canonical_id == "period:patriarchal"


def test_bible_kg_passage_canonical_id():
    pa = BibleKgPassage(
        book_num=1,
        chapter=12,
        verse_start=1,
        verse_end=3,
        mentions_people=("person:abraham",),
        mentions_places=("place:haran",),
        period_slug="patriarchal",
    )
    assert pa.canonical_id == "passage:1:12:1-3"


def test_bible_kg_passage_canonical_id_variants():
    """canonical_id varía según presencia de verse_start/verse_end."""
    chapter_only = BibleKgPassage(book_num=1, chapter=12)
    assert chapter_only.canonical_id == "passage:1:12"

    single_verse = BibleKgPassage(book_num=1, chapter=12, verse_start=1)
    assert single_verse.canonical_id == "passage:1:12:1"

    same_start_end = BibleKgPassage(book_num=1, chapter=12, verse_start=1, verse_end=1)
    assert same_start_end.canonical_id == "passage:1:12:1"


def test_models_are_frozen():
    """ConfigDict(frozen=True) bloquea mutación en runtime."""
    p = BibleKgPerson(slug="abraham", name="Abraham")
    with pytest.raises(ValidationError):
        p.name = "Abram"  # type: ignore[misc]
