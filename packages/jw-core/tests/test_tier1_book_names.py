"""Confirm Tier-1 book-name expansion lets parse_reference work in fr/de/it/etc."""

from __future__ import annotations

import pytest

from jw_core.data.books import BOOKS
from jw_core.parsers.reference import parse_reference
from jw_core.translation import render_reference


def test_books_have_tier1_languages() -> None:
    for entry in BOOKS:
        for lang in ("fr", "de", "it", "ru", "ja", "ko", "zh"):
            assert lang in entry["names"], f"book {entry['num']} missing {lang}"
            assert entry["names"][lang], f"book {entry['num']} empty list for {lang}"


@pytest.mark.parametrize(
    "text,expected_book",
    [
        ("Genèse 1:1", 1),
        ("Romains 12:2", 45),
        ("1. Mose 1:1", 1),  # German: 1. Mose
        ("Römer 12:2", 45),  # German Romans
        ("Genesi 1:1", 1),
        ("Romani 12:2", 45),
        ("Бытие 1:1", 1),
        ("Римлянам 12:2", 45),
        ("창세기 1:1", 1),
        ("로마서 12:2", 45),
        ("创世记 1:1", 1),
        ("罗马书 12:2", 45),
        ("創世記 1:1", 1),  # Japanese
    ],
)
def test_parse_reference_recognises_tier1_languages(text: str, expected_book: int) -> None:
    ref = parse_reference(text)
    assert ref is not None, f"parser failed on {text!r}"
    assert ref.book_num == expected_book


def test_render_reference_in_new_language() -> None:
    assert render_reference(book_num=43, chapter=3, verse_start=16, language="fr") == "Jean 3:16"
    assert render_reference(book_num=43, chapter=3, verse_start=16, language="de") == "Johannes 3:16"
    assert render_reference(book_num=43, chapter=3, verse_start=16, language="ko") == "요한 3:16"
