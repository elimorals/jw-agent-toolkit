"""Tests for the study-book registry."""

from __future__ import annotations

import pytest
from jw_core.data.study_books import (
    CURRENT_STUDY_BOOK,
    REGISTRY,
    get_book,
    list_supported_languages,
)


def test_current_study_book_is_lff() -> None:
    assert CURRENT_STUDY_BOOK == "lff"
    assert "lff" in REGISTRY


def test_lff_metadata_complete() -> None:
    book = get_book("lff")
    assert book.pub_code == "lff"
    assert book.title_by_lang["es"].startswith("Disfruta")
    assert book.title_by_lang["en"].startswith("Enjoy")
    assert book.total_chapters == 60
    assert "es" in book.languages
    assert "en" in book.languages
    assert "pt" in book.languages


def test_get_book_unknown_raises() -> None:
    with pytest.raises(KeyError):
        get_book("does_not_exist")


def test_list_supported_languages_returns_union() -> None:
    langs = list_supported_languages()
    assert "es" in langs
    assert "en" in langs
    assert "pt" in langs


def test_registry_entries_are_frozen() -> None:
    book = get_book("lff")
    with pytest.raises(Exception):  # FrozenInstanceError
        book.pub_code = "x"  # type: ignore[misc]
