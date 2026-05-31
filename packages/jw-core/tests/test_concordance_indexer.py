"""Tests for jw_core.concordance.indexer — EPUB + NWT adapters."""

from __future__ import annotations

from pathlib import Path

from jw_core.concordance.indexer import (
    NWTChapter,
    _file_sha256,
    build_index,
    index_epub,
    index_nwt_chapter,
)
from jw_core.concordance.store import ConcordanceStore
from tests.fixtures.concordance import build_minimal_epub


def test_index_nwt_chapter_inserts_one_per_verse(tmp_path: Path) -> None:
    store = ConcordanceStore(db_path=tmp_path / "c.db")
    try:
        chapter = NWTChapter(
            language="es",
            book_num=43,
            chapter=3,
            verses=[
                (15, "Para que todo el que ejerce fe en él tenga vida eterna."),
                (16, "Porque tanto amó Dios al mundo que dio a su Hijo unigénito."),
            ],
            url="https://wol.jw.org/es/wol/b/r4/lp-s/nwt/E/2024/43/3",
        )
        n = index_nwt_chapter(store, chapter)
        assert n == 2
        rows = list(store.iter_entries())
        assert rows[0].source_kind == "nwt"
        assert "3:15" in rows[0].ref
        assert rows[0].url is not None
        assert rows[0].language == "es"
    finally:
        store.close()


def test_index_epub_chunks_by_paragraph(tmp_path: Path) -> None:
    epub = build_minimal_epub(
        tmp_path / "demo.epub",
        title="Demo",
        paragraphs=[
            "Conocer al Dios verdadero requiere conocimiento exacto.",
            "La fe se basa en hechos, no en sentimientos vagos.",
        ],
    )
    store = ConcordanceStore(db_path=tmp_path / "c.db")
    try:
        n = index_epub(store, epub, language="es")
        assert n == 2
        kinds = {e.source_kind for e in store.iter_entries()}
        assert kinds == {"epub"}
    finally:
        store.close()


def test_build_index_dispatches_by_extension(tmp_path: Path) -> None:
    epub = build_minimal_epub(
        tmp_path / "demo.epub",
        title="Demo",
        paragraphs=["literal phrase one", "literal phrase two"],
    )
    n = build_index(paths=[epub], language="en", db_path=tmp_path / "c.db")
    assert n == 2


def test_build_index_skips_known_source(tmp_path: Path) -> None:
    epub = build_minimal_epub(
        tmp_path / "demo.epub",
        title="Demo",
        paragraphs=["paragraph one", "paragraph two"],
    )
    db = tmp_path / "c.db"
    first = build_index(paths=[epub], language="en", db_path=db)
    second = build_index(paths=[epub], language="en", db_path=db)
    assert first == 2
    assert second == 0  # sha256 unchanged ⇒ skipped


def test_build_index_force_reindexes(tmp_path: Path) -> None:
    epub = build_minimal_epub(
        tmp_path / "demo.epub",
        title="Demo",
        paragraphs=["only one"],
    )
    db = tmp_path / "c.db"
    build_index(paths=[epub], language="en", db_path=db)
    n = build_index(paths=[epub], language="en", db_path=db, force=True)
    assert n == 1
    # And the count is still 1, not 2 — replace_source did its job.
    store = ConcordanceStore(db_path=db)
    try:
        assert store.count() == 1
    finally:
        store.close()


def test_file_sha256_deterministic(tmp_path: Path) -> None:
    p = tmp_path / "x.bin"
    p.write_bytes(b"hello world")
    digest_a = _file_sha256(p)
    digest_b = _file_sha256(p)
    assert digest_a == digest_b
    assert len(digest_a) == 64


def test_build_index_accepts_pure_nwt_input(tmp_path: Path) -> None:
    ch = NWTChapter(
        language="es",
        book_num=43,
        chapter=3,
        verses=[(16, "Porque tanto amó Dios al mundo")],
        url="https://wol.jw.org/es/wol/b/r4/lp-s/nwt/E/2024/43/3",
    )
    n = build_index(paths=None, language="es", db_path=tmp_path / "c.db", nwt_chapters=[ch])
    assert n == 1
