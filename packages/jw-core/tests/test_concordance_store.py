"""Tests for jw_core.concordance.store — schema, insert, dedupe."""

from __future__ import annotations

from pathlib import Path

import pytest

from jw_core.concordance.models import IndexEntry
from jw_core.concordance.store import ConcordanceStore, default_db_path


def _entry(text: str, **overrides: object) -> IndexEntry:
    defaults: dict[str, object] = {
        "source_kind": "epub",
        "source_id": "fake-1",
        "ref": "item-1:p0",
        "chunk_text": text,
        "language": "en",
    }
    defaults.update(overrides)
    return IndexEntry.model_validate(defaults)


def test_store_initializes_schema(tmp_path: Path) -> None:
    db = tmp_path / "c.db"
    store = ConcordanceStore(db_path=db)
    try:
        # FTS5 virtual table must exist
        names = {row[0] for row in store._conn.execute("SELECT name FROM sqlite_master WHERE type IN ('table','view')")}
        assert "concordance_entries" in names
        assert "concordance_fts" in names
        assert "concordance_sources" in names
    finally:
        store.close()


def test_default_db_path_resolves_under_home(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv("JW_CONCORDANCE_DB", raising=False)
    p = default_db_path()
    assert str(p).endswith("/.jw-agent-toolkit/concordance.db")
    monkeypatch.setenv("JW_CONCORDANCE_DB", str(tmp_path / "alt.db"))
    p2 = default_db_path()
    assert p2 == tmp_path / "alt.db"


def test_add_and_count(tmp_path: Path) -> None:
    store = ConcordanceStore(db_path=tmp_path / "c.db")
    try:
        n = store.add_many([_entry("Hello world"), _entry("Second line")])
        assert n == 2
        assert store.count() == 2
    finally:
        store.close()


def test_replace_source_atomically(tmp_path: Path) -> None:
    store = ConcordanceStore(db_path=tmp_path / "c.db")
    try:
        store.add_many([_entry("A", source_id="src1"), _entry("B", source_id="src1")])
        # Re-ingesting src1 should remove the old two and insert the new one.
        store.replace_source(
            source_kind="epub",
            source_id="src1",
            entries=[_entry("C", source_id="src1")],
        )
        rows = list(store.iter_entries())
        assert len(rows) == 1
        assert rows[0].chunk_text == "C"
    finally:
        store.close()


def test_known_source_dedupe(tmp_path: Path) -> None:
    store = ConcordanceStore(db_path=tmp_path / "c.db")
    try:
        assert store.is_known_source("epub", "/tmp/x.epub", "deadbeef") is False
        store.mark_source(
            source_kind="epub",
            source_path="/tmp/x.epub",
            source_sha256="deadbeef",
            language="en",
            n_entries=3,
        )
        assert store.is_known_source("epub", "/tmp/x.epub", "deadbeef") is True
        assert store.is_known_source("epub", "/tmp/x.epub", "OTHER") is False
    finally:
        store.close()


def test_wal_mode_set(tmp_path: Path) -> None:
    store = ConcordanceStore(db_path=tmp_path / "c.db")
    try:
        mode = store._conn.execute("PRAGMA journal_mode").fetchone()[0]
        assert mode.lower() == "wal"
    finally:
        store.close()
