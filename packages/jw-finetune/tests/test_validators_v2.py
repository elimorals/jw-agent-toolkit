"""Tests for the F6.4 validators using jw_core.parsers.reference."""

from __future__ import annotations

from jw_finetune.synth import validators


def test_bible_ref_full_name_es() -> None:
    assert validators.is_valid_bible_ref("Génesis 1:1 lo dice")
    assert validators.is_valid_bible_ref("según Mateo 24:14")


def test_bible_ref_abbrev_es() -> None:
    # WBTS abbreviation forms
    assert validators.is_valid_bible_ref("Mt 24:14") or validators.is_valid_bible_ref("Mat 24:14")


def test_bible_ref_with_book_prefix_es() -> None:
    assert validators.is_valid_bible_ref("1 Corintios 13:4-7 nos enseña")


def test_bible_ref_no_match_returns_false() -> None:
    assert not validators.is_valid_bible_ref("hola mundo, esto no tiene refs.")
    assert not validators.is_valid_bible_ref("")


def test_count_bible_refs_multiple() -> None:
    text = "Como dice Mateo 24:14 y Hechos 1:8, debemos predicar."
    assert validators.count_bible_refs(text) >= 1


def test_count_bible_refs_zero() -> None:
    assert validators.count_bible_refs("ningún versículo aquí") == 0


def test_bible_ref_english() -> None:
    # The parser is language-aware and should accept English book names.
    assert validators.is_valid_bible_ref("As Matthew 24:14 says")
