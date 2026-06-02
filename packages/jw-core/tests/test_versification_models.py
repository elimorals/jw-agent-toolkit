"""Tests for versification Pydantic models."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from jw_core.versification.models import (
    MappingResult,
    Tradition,
    VerseCoord,
    VersificationMapping,
)


def test_verse_coord_basic() -> None:
    c = VerseCoord(chapter=51, verse_start=1)
    assert c.chapter == 51
    assert c.verse_start == 1
    assert c.verse_end is None


def test_verse_coord_allows_superscription_verse_zero() -> None:
    c = VerseCoord(chapter=51, verse_start=0)
    assert c.verse_start == 0


def test_verse_coord_rejects_negative() -> None:
    with pytest.raises(ValidationError):
        VerseCoord(chapter=-1, verse_start=1)
    with pytest.raises(ValidationError):
        VerseCoord(chapter=51, verse_start=-1)


def test_verse_coord_range() -> None:
    c = VerseCoord(chapter=2, verse_start=28, verse_end=32)
    assert c.verse_end == 32


def test_tradition_literal_values() -> None:
    valid: list[Tradition] = ["nwt", "masoretic", "lxx", "vulgate"]
    for t in valid:
        m = MappingResult(
            ref_book="Joel",
            ref_book_num=29,
            coord=VerseCoord(chapter=2, verse_start=28),
            from_tradition=t,
            to_tradition=t,
            is_discrepant=False,
        )
        assert m.from_tradition == t


def test_versification_mapping_minimal_nwt_to_masoretic() -> None:
    m = VersificationMapping(
        book="Joel",
        book_num=29,
        issue="chapter_renumber",
        nwt=VerseCoord(chapter=2, verse_start=28, verse_end=32),
        masoretic=VerseCoord(chapter=3, verse_start=1, verse_end=5),
        source="Tov 2012:32",
        explanation={
            "en": "Joel 2:28-32 in the NWT corresponds to Joel 3:1-5 in BHS.",
            "es": "Joel 2:28-32 en la NWT corresponde a Joel 3:1-5 en BHS.",
            "pt": "Joel 2:28-32 na TNM corresponde a Joel 3:1-5 na BHS.",
        },
    )
    assert m.book == "Joel"
    assert m.book_num == 29
    assert m.lxx is None
    assert m.vulgate is None
    assert m.nwt.verse_start == 28
    assert m.masoretic is not None
    assert m.masoretic.chapter == 3


def test_versification_mapping_requires_all_three_languages() -> None:
    with pytest.raises(ValidationError):
        VersificationMapping(
            book="Joel",
            book_num=29,
            issue="chapter_renumber",
            nwt=VerseCoord(chapter=2, verse_start=28),
            source="Tov 2012:32",
            explanation={"en": "only english"},  # type: ignore[arg-type]
        )


def test_versification_mapping_rejects_unknown_issue() -> None:
    with pytest.raises(ValidationError):
        VersificationMapping(
            book="Joel",
            book_num=29,
            issue="frobnicate",  # type: ignore[arg-type]
            nwt=VerseCoord(chapter=2, verse_start=28),
            source="x",
            explanation={"en": "x", "es": "x", "pt": "x"},
        )


def test_mapping_result_identity_case() -> None:
    r = MappingResult(
        ref_book="Genesis",
        ref_book_num=1,
        coord=VerseCoord(chapter=1, verse_start=1),
        from_tradition="nwt",
        to_tradition="nwt",
        is_discrepant=False,
    )
    assert r.is_discrepant is False
    assert r.rationale is None


def test_mapping_result_discrepant_carries_rationale() -> None:
    r = MappingResult(
        ref_book="Joel",
        ref_book_num=29,
        coord=VerseCoord(chapter=3, verse_start=1, verse_end=5),
        from_tradition="nwt",
        to_tradition="masoretic",
        is_discrepant=True,
        rationale="Joel 2:28-32 NWT to Joel 3:1-5 masoretic.",
    )
    assert r.is_discrepant is True
    assert r.rationale is not None and "Joel" in r.rationale
