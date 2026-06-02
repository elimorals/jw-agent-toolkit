"""Tests for the to_canonical mapping."""

from __future__ import annotations

import pytest
from jw_core.versification.mapping import to_canonical


def test_identity_when_traditions_match() -> None:
    r = to_canonical(
        book="Genesis",
        book_num=1,
        chapter=1,
        verse_start=1,
        from_tradition="nwt",
        to_tradition="nwt",
    )
    assert r.is_discrepant is False
    assert r.coord.chapter == 1 and r.coord.verse_start == 1


def test_uncataloged_passes_through_without_shift() -> None:
    r = to_canonical(
        book="John",
        book_num=43,
        chapter=3,
        verse_start=16,
        from_tradition="nwt",
        to_tradition="masoretic",
    )
    assert r.is_discrepant is False
    assert r.coord.chapter == 3 and r.coord.verse_start == 16


def test_joel_2_28_nwt_to_masoretic() -> None:
    r = to_canonical(
        book="Joel",
        book_num=29,
        chapter=2,
        verse_start=28,
        verse_end=32,
        from_tradition="nwt",
        to_tradition="masoretic",
    )
    assert r.is_discrepant is True
    assert r.coord.chapter == 3
    assert r.coord.verse_start == 1
    assert r.coord.verse_end == 5


def test_malachi_4_1_nwt_to_masoretic() -> None:
    r = to_canonical(
        book="Malachi",
        book_num=39,
        chapter=4,
        verse_start=1,
        verse_end=6,
        from_tradition="nwt",
        to_tradition="masoretic",
    )
    assert r.is_discrepant is True
    assert r.coord.chapter == 3
    assert r.coord.verse_start == 19
    assert r.coord.verse_end == 24


def test_psalm_51_superscription_nwt_to_lxx() -> None:
    r = to_canonical(
        book="Psalms",
        book_num=19,
        chapter=51,
        verse_start=1,
        from_tradition="nwt",
        to_tradition="lxx",
    )
    assert r.is_discrepant is True
    assert r.coord.chapter == 50
    assert r.coord.verse_start == 0


def test_round_trip_joel_2_28() -> None:
    forward = to_canonical(
        book="Joel",
        book_num=29,
        chapter=2,
        verse_start=28,
        verse_end=32,
        from_tradition="nwt",
        to_tradition="masoretic",
    )
    back = to_canonical(
        book=forward.ref_book,
        book_num=forward.ref_book_num,
        chapter=forward.coord.chapter,
        verse_start=forward.coord.verse_start,
        verse_end=forward.coord.verse_end,
        from_tradition="masoretic",
        to_tradition="nwt",
    )
    assert back.coord.chapter == 2
    assert back.coord.verse_start == 28
    assert back.coord.verse_end == 32


def test_round_trip_malachi_4() -> None:
    forward = to_canonical(
        book="Malachi",
        book_num=39,
        chapter=4,
        verse_start=1,
        verse_end=6,
        from_tradition="nwt",
        to_tradition="masoretic",
    )
    back = to_canonical(
        book=forward.ref_book,
        book_num=forward.ref_book_num,
        chapter=forward.coord.chapter,
        verse_start=forward.coord.verse_start,
        verse_end=forward.coord.verse_end,
        from_tradition="masoretic",
        to_tradition="nwt",
    )
    assert back.coord.chapter == 4
    assert back.coord.verse_start == 1
    assert back.coord.verse_end == 6


def test_unknown_tradition_raises() -> None:
    with pytest.raises(ValueError, match="from_tradition"):
        to_canonical(
            book="Genesis",
            book_num=1,
            chapter=1,
            verse_start=1,
            from_tradition="aramaic",  # type: ignore[arg-type]
            to_tradition="nwt",
        )
    with pytest.raises(ValueError, match="to_tradition"):
        to_canonical(
            book="Genesis",
            book_num=1,
            chapter=1,
            verse_start=1,
            from_tradition="nwt",
            to_tradition="aramaic",  # type: ignore[arg-type]
        )
