"""Tests for jw_core.concordance.search — phrase, AND/OR, snippet markers."""

from __future__ import annotations

from pathlib import Path

from jw_core.concordance.indexer import NWTChapter, index_nwt_chapter
from jw_core.concordance.search import (
    SNIPPET_END,
    SNIPPET_START,
    concordance_search,
    escape_fts_phrase,
    is_safe_query,
)
from jw_core.concordance.store import ConcordanceStore


def _seed(db: Path) -> None:
    store = ConcordanceStore(db_path=db)
    try:
        chapters = [
            NWTChapter(
                language="es",
                book_num=43,
                chapter=3,
                verses=[
                    (15, "Para que todo el que ejerce fe en él tenga vida eterna."),
                    (16, "Porque tanto amó Dios al mundo que dio a su Hijo unigénito."),
                ],
                url="https://wol.jw.org/es/wol/b/r4/lp-s/nwt/E/2024/43/3",
            ),
            NWTChapter(
                language="en",
                book_num=43,
                chapter=3,
                verses=[
                    (16, "For God loved the world so much that he gave his only-begotten Son."),
                ],
                url="https://wol.jw.org/en/wol/b/r1/lp-e/nwt/E/2024/43/3",
            ),
        ]
        for ch in chapters:
            index_nwt_chapter(store, ch)
    finally:
        store.close()


def test_phrase_search_finds_exact_match(tmp_path: Path) -> None:
    _seed(tmp_path / "c.db")
    hits = concordance_search('"amó Dios al mundo"', db_path=tmp_path / "c.db")
    assert len(hits) >= 1
    assert any("amó Dios al mundo" in h.snippet.replace(SNIPPET_START, "").replace(SNIPPET_END, "") for h in hits)
    assert hits[0].url is not None


def test_language_filter(tmp_path: Path) -> None:
    _seed(tmp_path / "c.db")
    en_hits = concordance_search("world", language="en", db_path=tmp_path / "c.db")
    es_hits = concordance_search("mundo", language="es", db_path=tmp_path / "c.db")
    assert all(h.language == "en" for h in en_hits)
    assert all(h.language == "es" for h in es_hits)


def test_source_kind_filter(tmp_path: Path) -> None:
    _seed(tmp_path / "c.db")
    hits = concordance_search("mundo", source_kind="nwt", db_path=tmp_path / "c.db")
    assert hits
    assert all(h.source_kind == "nwt" for h in hits)


def test_snippet_carries_markers(tmp_path: Path) -> None:
    _seed(tmp_path / "c.db")
    hits = concordance_search("amó", db_path=tmp_path / "c.db", language="es")
    assert hits
    assert SNIPPET_START in hits[0].snippet
    assert SNIPPET_END in hits[0].snippet


def test_diacritic_insensitive_matches(tmp_path: Path) -> None:
    # unicode61 remove_diacritics=2 means 'amo' should still hit 'amó'.
    _seed(tmp_path / "c.db")
    hits = concordance_search("amo", language="es", db_path=tmp_path / "c.db")
    assert hits, "diacritic-insensitive tokenizer should match"


def test_or_query(tmp_path: Path) -> None:
    _seed(tmp_path / "c.db")
    hits = concordance_search("amó OR ejerce", language="es", db_path=tmp_path / "c.db")
    # Both verses contain at least one of the terms.
    assert len(hits) == 2


def test_max_results_caps(tmp_path: Path) -> None:
    db = tmp_path / "c.db"
    store = ConcordanceStore(db_path=db)
    try:
        chapter = NWTChapter(
            language="en",
            book_num=1,
            chapter=1,
            verses=[(i, f"line {i} contains repeat token") for i in range(1, 50)],
            url=None,
        )
        index_nwt_chapter(store, chapter)
    finally:
        store.close()
    hits = concordance_search("repeat", db_path=db, max_results=5)
    assert len(hits) == 5


def test_escape_fts_phrase_quotes_terms() -> None:
    assert escape_fts_phrase("hello world") == '"hello world"'
    # Embedded double quotes are doubled per FTS5 conventions.
    assert escape_fts_phrase('say "hi"') == '"say ""hi"""'


def test_is_safe_query_rejects_regex_metacharacters() -> None:
    assert is_safe_query('"hello"') is True
    assert is_safe_query("a OR b") is True
    assert is_safe_query(r"\bword\b") is False
    assert is_safe_query("[abc]+") is False


def test_empty_db_returns_empty(tmp_path: Path) -> None:
    db = tmp_path / "c.db"
    ConcordanceStore(db_path=db).close()
    assert concordance_search("anything", db_path=db) == []
