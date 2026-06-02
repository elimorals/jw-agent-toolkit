"""Tests for the trilingual explain helper."""

from __future__ import annotations

from jw_core.versification.explain import explain


def test_explain_identity_returns_none() -> None:
    assert (
        explain(
            book="Genesis",
            book_num=1,
            chapter=1,
            verse_start=1,
            from_tradition="nwt",
            to_tradition="nwt",
        )
        is None
    )


def test_explain_uncataloged_returns_none() -> None:
    assert (
        explain(
            book="John",
            book_num=43,
            chapter=3,
            verse_start=16,
            from_tradition="nwt",
            to_tradition="masoretic",
        )
        is None
    )


def test_explain_joel_2_28_in_three_languages() -> None:
    en = explain(
        book="Joel",
        book_num=29,
        chapter=2,
        verse_start=28,
        from_tradition="nwt",
        to_tradition="masoretic",
        language="en",
    )
    es = explain(
        book="Joel",
        book_num=29,
        chapter=2,
        verse_start=28,
        from_tradition="nwt",
        to_tradition="masoretic",
        language="es",
    )
    pt = explain(
        book="Joel",
        book_num=29,
        chapter=2,
        verse_start=28,
        from_tradition="nwt",
        to_tradition="masoretic",
        language="pt",
    )
    assert en is not None and "Joel" in en and "Masoretic" in en
    assert es is not None and "Joel" in es and "masorético" in es
    assert pt is not None and "Joel" in pt and "Massorético" in pt


def test_explain_malachi_4_masoretic() -> None:
    s = explain(
        book="Malachi",
        book_num=39,
        chapter=4,
        verse_start=1,
        from_tradition="nwt",
        to_tradition="masoretic",
        language="en",
    )
    assert s is not None and "Malachi" in s
