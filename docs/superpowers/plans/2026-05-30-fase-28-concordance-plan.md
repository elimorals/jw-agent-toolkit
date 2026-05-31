# Fase 28 — Concordancia exacta · Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship deterministic exact-phrase concordance over the locally-decrypted JW corpus (NWT + JWPUB + EPUB), backed by SQLite FTS5, exposed via CLI (`jw grep`) and MCP (`concordance_*`).

**Architecture:** New module `jw_core.concordance` (inside `jw-core`, not a new package — reuses the FTS5 pattern from `jw_core.study.personal_notes`). DB at `~/.jw-agent-toolkit/concordance.db`. Indexer adapters route by source kind and chunk by paragraph (verse for NWT). Snippet via FTS5 `snippet()` with `‹…›` markers.

**Tech Stack:** Python 3.13 · `sqlite3` (stdlib, FTS5 built-in) · Pydantic v2 · Typer (CLI) · FastMCP (MCP tools) · existing `jw_core.parsers.{jwpub, epub}`.

**Spec:** [`docs/superpowers/specs/2026-05-30-fase-28-concordance-design.md`](../specs/2026-05-30-fase-28-concordance-design.md).

---

## File map

Creates:
- `packages/jw-core/src/jw_core/concordance/__init__.py`
- `packages/jw-core/src/jw_core/concordance/models.py`
- `packages/jw-core/src/jw_core/concordance/store.py`
- `packages/jw-core/src/jw_core/concordance/indexer.py`
- `packages/jw-core/src/jw_core/concordance/search.py`
- `packages/jw-core/tests/test_concordance_store.py`
- `packages/jw-core/tests/test_concordance_indexer.py`
- `packages/jw-core/tests/test_concordance_search.py`
- `packages/jw-core/tests/fixtures/concordance/demo.epub` (synthetic, built by helper in test)
- `packages/jw-cli/src/jw_cli/commands/grep.py`
- `packages/jw-mcp/src/jw_mcp/tools/concordance.py`
- `docs/guias/concordancia-exacta.md`

Modifies:
- `packages/jw-cli/src/jw_cli/main.py` — register `grep` command.
- `packages/jw-cli/src/jw_cli/commands/__init__.py` — re-export.
- `packages/jw-mcp/src/jw_mcp/server.py` — register two MCP tools.
- `docs/ROADMAP.md` — add Fase 28 section.
- `docs/VISION_AUDIT.md` — flag concordance feature as covered.
- `docs/README.md` — link the new guide.

---

### Task 1: Pydantic models (`IndexEntry`, `ConcordanceHit`)

**Files:**
- Create: `packages/jw-core/src/jw_core/concordance/__init__.py`
- Create: `packages/jw-core/src/jw_core/concordance/models.py`
- Create: `packages/jw-core/tests/test_concordance_models.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/jw-core/tests/test_concordance_models.py
"""Tests for jw_core.concordance.models."""

from __future__ import annotations

import pytest

from jw_core.concordance.models import ConcordanceHit, IndexEntry


def test_index_entry_minimal() -> None:
    e = IndexEntry(
        source_kind="nwt",
        source_id="nwt:es:43:3",
        ref="Juan 3:16",
        chunk_text="Porque tanto amó Dios al mundo...",
        language="es",
    )
    assert e.source_kind == "nwt"
    assert e.url is None
    assert e.source_sha256 == ""


def test_index_entry_rejects_invalid_kind() -> None:
    with pytest.raises(ValueError):
        IndexEntry(
            source_kind="bogus",  # type: ignore[arg-type]
            source_id="x",
            ref="x",
            chunk_text="x",
            language="en",
        )


def test_concordance_hit_carries_snippet_with_markers() -> None:
    h = ConcordanceHit(
        entry_id=1,
        source_kind="epub",
        source_id="abc",
        ref="item-3:p5",
        snippet="...esto es ‹prueba› literal...",
        language="en",
        url=None,
    )
    assert "‹prueba›" in h.snippet
    assert h.url is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/jw-core/tests/test_concordance_models.py -v`
Expected: FAIL — `jw_core.concordance` not found.

- [ ] **Step 3: Implement the models + package init**

```python
# packages/jw-core/src/jw_core/concordance/__init__.py
"""Exact-match concordance over the local decrypted JW corpus.

Public API:
    from jw_core.concordance import (
        build_index,
        concordance_search,
        ConcordanceHit,
        IndexEntry,
        ConcordanceStore,
        default_db_path,
    )

See `docs/superpowers/specs/2026-05-30-fase-28-concordance-design.md`.
"""

from jw_core.concordance.indexer import build_index
from jw_core.concordance.models import ConcordanceHit, IndexEntry
from jw_core.concordance.search import concordance_search
from jw_core.concordance.store import ConcordanceStore, default_db_path

__all__ = [
    "ConcordanceHit",
    "ConcordanceStore",
    "IndexEntry",
    "build_index",
    "concordance_search",
    "default_db_path",
]
```

```python
# packages/jw-core/src/jw_core/concordance/models.py
"""Pydantic models for the concordance index."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

SourceKind = Literal["nwt", "jwpub", "epub"]


class IndexEntry(BaseModel):
    """One row inserted into `concordance_entries`.

    The pair (source_kind, source_id) identifies the document; `ref` is the
    human-readable citation anchor (e.g. "Juan 3:16" or "doc#42 p7").
    """

    source_kind: SourceKind
    source_id: str
    ref: str
    chunk_text: str
    language: str
    url: str | None = None
    source_path: str | None = None
    source_sha256: str = ""


class ConcordanceHit(BaseModel):
    """One result returned by `concordance_search`."""

    entry_id: int
    source_kind: SourceKind
    source_id: str
    ref: str
    snippet: str  # FTS5 snippet() output with ‹…› markers around the match
    language: str
    url: str | None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest packages/jw-core/tests/test_concordance_models.py -v`
Expected: 3 passed.

Note: the `__init__.py` imports `build_index`, `concordance_search`, and `ConcordanceStore` which don't exist yet — keep `__init__.py` empty (just the docstring + an `__all__ = []`) until Task 4 lands, OR comment the imports out for now and re-enable at Task 4 step 5. The TDD test above only needs `models.py` imported via the full path, which it does.

Apply this minimal stub instead until Task 4:

```python
# packages/jw-core/src/jw_core/concordance/__init__.py (interim)
"""Exact-match concordance — public API completes at Task 4."""

from jw_core.concordance.models import ConcordanceHit, IndexEntry

__all__ = ["ConcordanceHit", "IndexEntry"]
```

- [ ] **Step 5: Commit**

```bash
git add packages/jw-core/src/jw_core/concordance packages/jw-core/tests/test_concordance_models.py
git commit -m "feat(concordance): Pydantic models for IndexEntry and ConcordanceHit"
```

---

### Task 2: `ConcordanceStore` — SQLite FTS5 with WAL

**Files:**
- Create: `packages/jw-core/src/jw_core/concordance/store.py`
- Create: `packages/jw-core/tests/test_concordance_store.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/jw-core/tests/test_concordance_store.py
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/jw-core/tests/test_concordance_store.py -v`
Expected: FAIL — `store` module missing.

- [ ] **Step 3: Implement the store**

```python
# packages/jw-core/src/jw_core/concordance/store.py
"""SQLite FTS5 store for the concordance index.

Schema (see spec for full DDL):
    concordance_entries — one row per indexed paragraph/verse.
    concordance_fts     — FTS5 virtual table mirroring `chunk_text`,
                          tokenize='unicode61 remove_diacritics 2'.
    concordance_sources — sha256 cache for incremental re-indexing.

WAL mode is enabled so the indexer and concurrent readers (CLI / MCP)
don't deadlock. Triggers keep the FTS5 mirror in sync.
"""

from __future__ import annotations

import os
import sqlite3
import time
from collections.abc import Iterable, Iterator
from pathlib import Path

from jw_core.concordance.models import IndexEntry, SourceKind


def default_db_path() -> Path:
    """Resolve the on-disk DB location, honouring JW_CONCORDANCE_DB."""

    return Path(
        os.getenv("JW_CONCORDANCE_DB", "~/.jw-agent-toolkit/concordance.db")
    ).expanduser()


_SCHEMA = """
CREATE TABLE IF NOT EXISTS concordance_entries (
    entry_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    source_kind   TEXT NOT NULL,
    source_id     TEXT NOT NULL,
    ref           TEXT NOT NULL,
    chunk_text    TEXT NOT NULL,
    language      TEXT NOT NULL,
    url           TEXT,
    source_path   TEXT,
    source_sha256 TEXT NOT NULL DEFAULT '',
    indexed_at_unix REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_conc_source ON concordance_entries (source_kind, source_id);
CREATE INDEX IF NOT EXISTS idx_conc_sha    ON concordance_entries (source_sha256);

CREATE VIRTUAL TABLE IF NOT EXISTS concordance_fts USING fts5(
    chunk_text,
    content='concordance_entries',
    content_rowid='entry_id',
    tokenize='unicode61 remove_diacritics 2'
);

CREATE TRIGGER IF NOT EXISTS conc_ai AFTER INSERT ON concordance_entries BEGIN
    INSERT INTO concordance_fts(rowid, chunk_text) VALUES (new.entry_id, new.chunk_text);
END;
CREATE TRIGGER IF NOT EXISTS conc_ad AFTER DELETE ON concordance_entries BEGIN
    INSERT INTO concordance_fts(concordance_fts, rowid, chunk_text)
    VALUES('delete', old.entry_id, old.chunk_text);
END;

CREATE TABLE IF NOT EXISTS concordance_sources (
    source_kind     TEXT NOT NULL,
    source_path     TEXT NOT NULL,
    source_sha256   TEXT NOT NULL,
    language        TEXT NOT NULL,
    n_entries       INTEGER NOT NULL,
    indexed_at_unix REAL NOT NULL,
    PRIMARY KEY (source_kind, source_path)
);
"""


class ConcordanceStore:
    """Wrap an FTS5-backed SQLite database for the concordance index."""

    def __init__(self, db_path: Path | str | None = None) -> None:
        self.path = Path(db_path).expanduser() if db_path else default_db_path()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.path, isolation_level=None, timeout=5.0)
        self._conn.row_factory = sqlite3.Row
        # Validate FTS5 availability up front with a clearly-actionable error.
        try:
            self._conn.execute("CREATE VIRTUAL TABLE IF NOT EXISTS _fts_probe USING fts5(x)")
            self._conn.execute("DROP TABLE _fts_probe")
        except sqlite3.OperationalError as exc:
            self._conn.close()
            raise RuntimeError(
                "SQLite FTS5 is unavailable in this Python build. "
                "Reinstall Python 3.13 with a sqlite3 that includes FTS5."
            ) from exc
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=NORMAL")
        self._conn.executescript(_SCHEMA)

    # ── Inserts ────────────────────────────────────────────────────────

    def add_many(self, entries: Iterable[IndexEntry]) -> int:
        """Insert a batch of entries. Returns the number of rows written."""

        rows = [
            (
                e.source_kind,
                e.source_id,
                e.ref,
                e.chunk_text,
                e.language,
                e.url,
                e.source_path,
                e.source_sha256,
                time.time(),
            )
            for e in entries
        ]
        if not rows:
            return 0
        with self._conn:
            self._conn.executemany(
                "INSERT INTO concordance_entries "
                "(source_kind, source_id, ref, chunk_text, language, url, "
                " source_path, source_sha256, indexed_at_unix) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                rows,
            )
        return len(rows)

    def replace_source(
        self,
        *,
        source_kind: SourceKind,
        source_id: str,
        entries: list[IndexEntry],
    ) -> int:
        """Atomically replace every entry for (kind, source_id)."""

        with self._conn:
            self._conn.execute(
                "DELETE FROM concordance_entries WHERE source_kind = ? AND source_id = ?",
                (source_kind, source_id),
            )
        return self.add_many(entries)

    # ── Source-level dedupe cache ──────────────────────────────────────

    def mark_source(
        self,
        *,
        source_kind: SourceKind,
        source_path: str,
        source_sha256: str,
        language: str,
        n_entries: int,
    ) -> None:
        with self._conn:
            self._conn.execute(
                "INSERT OR REPLACE INTO concordance_sources "
                "(source_kind, source_path, source_sha256, language, n_entries, indexed_at_unix) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (source_kind, source_path, source_sha256, language, n_entries, time.time()),
            )

    def is_known_source(self, kind: SourceKind, path: str, sha256: str) -> bool:
        row = self._conn.execute(
            "SELECT 1 FROM concordance_sources "
            "WHERE source_kind = ? AND source_path = ? AND source_sha256 = ? LIMIT 1",
            (kind, path, sha256),
        ).fetchone()
        return row is not None

    # ── Read helpers ───────────────────────────────────────────────────

    def count(self) -> int:
        return int(self._conn.execute("SELECT COUNT(*) FROM concordance_entries").fetchone()[0])

    def iter_entries(self) -> Iterator[IndexEntry]:
        for row in self._conn.execute(
            "SELECT source_kind, source_id, ref, chunk_text, language, url, "
            "source_path, source_sha256 FROM concordance_entries ORDER BY entry_id"
        ):
            yield IndexEntry(
                source_kind=row["source_kind"],
                source_id=row["source_id"],
                ref=row["ref"],
                chunk_text=row["chunk_text"],
                language=row["language"],
                url=row["url"],
                source_path=row["source_path"],
                source_sha256=row["source_sha256"] or "",
            )

    def stats(self) -> dict[str, int]:
        rows = self._conn.execute(
            "SELECT source_kind, COUNT(*) AS n FROM concordance_entries GROUP BY source_kind"
        ).fetchall()
        return {row["source_kind"]: int(row["n"]) for row in rows}

    # ── Lifecycle ──────────────────────────────────────────────────────

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> ConcordanceStore:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest packages/jw-core/tests/test_concordance_store.py -v`
Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add packages/jw-core/src/jw_core/concordance/store.py packages/jw-core/tests/test_concordance_store.py
git commit -m "feat(concordance): SQLite FTS5 store with WAL and source dedupe"
```

---

### Task 3: Indexer adapters (NWT chapter / JWPUB / EPUB)

**Files:**
- Create: `packages/jw-core/src/jw_core/concordance/indexer.py`
- Create: `packages/jw-core/tests/test_concordance_indexer.py`
- Create: `packages/jw-core/tests/fixtures/concordance/__init__.py` (helpers)

- [ ] **Step 1: Add a synthetic-EPUB helper for tests**

```python
# packages/jw-core/tests/fixtures/concordance/__init__.py
"""Builders for synthetic JWPUB/EPUB fixtures used by concordance tests.

We don't ship real JW publications in the repo (copyright). These
builders write structurally-valid minimal files we can index in tests.
"""

from __future__ import annotations

import io
import zipfile
from pathlib import Path


def build_minimal_epub(path: Path, *, title: str, paragraphs: list[str]) -> Path:
    """Write a minimal but spec-compliant EPUB to `path`."""

    container = """<?xml version="1.0"?>
<container xmlns="urn:oasis:names:tc:opendocument:xmlns:container" version="1.0">
  <rootfiles>
    <rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>
  </rootfiles>
</container>"""

    opf = f"""<?xml version="1.0"?>
<package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="i">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:title>{title}</dc:title>
    <dc:language>en</dc:language>
    <dc:identifier id="i">demo-1</dc:identifier>
  </metadata>
  <manifest>
    <item id="c1" href="ch1.xhtml" media-type="application/xhtml+xml"/>
  </manifest>
  <spine>
    <itemref idref="c1"/>
  </spine>
</package>"""

    body_paras = "\n".join(
        f'<p data-pid="{i}">{text}</p>' for i, text in enumerate(paragraphs)
    )
    xhtml = f"""<?xml version="1.0"?>
<html xmlns="http://www.w3.org/1999/xhtml">
  <head><title>{title}</title></head>
  <body>{body_paras}</body>
</html>"""

    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("META-INF/container.xml", container)
        z.writestr("OEBPS/content.opf", opf)
        z.writestr("OEBPS/ch1.xhtml", xhtml)
    return path
```

- [ ] **Step 2: Write the failing test**

```python
# packages/jw-core/tests/test_concordance_indexer.py
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
```

- [ ] **Step 3: Run test to verify it fails**

Run: `uv run pytest packages/jw-core/tests/test_concordance_indexer.py -v`
Expected: FAIL — indexer module missing.

- [ ] **Step 4: Implement the indexer**

```python
# packages/jw-core/src/jw_core/concordance/indexer.py
"""Indexer adapters that turn NWT chapters / JWPUB / EPUB into IndexEntry rows.

The indexer is the only place that touches the disk parsers; the store
stays I/O-agnostic. The indexer does **not** hit the network — for NWT
chapters the caller passes a pre-fetched `NWTChapter` (constructed by the
CLI/MCP layer from `WOLClient`).
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path

from jw_core.concordance.models import IndexEntry
from jw_core.concordance.store import ConcordanceStore
from jw_core.parsers.epub import parse_epub
from jw_core.parsers.jwpub import JwpubError, parse_jwpub


# ── Public types ──────────────────────────────────────────────────────


@dataclass
class NWTChapter:
    """A pre-fetched Bible chapter ready to be indexed.

    The CLI (or any caller) constructs this from `WOLClient.get_bible_chapter`
    output plus the chapter parser; we keep the concordance module HTTP-free.
    """

    language: str
    book_num: int
    chapter: int
    verses: list[tuple[int, str]]
    url: str | None = None
    book_name: str = ""
    publication: str = "nwt"

    def source_id(self) -> str:
        return f"nwt:{self.language}:{self.book_num}:{self.chapter}"

    def ref_for(self, verse: int) -> str:
        book = self.book_name or str(self.book_num)
        return f"{book} {self.chapter}:{verse}"


# ── Helpers ───────────────────────────────────────────────────────────


def _file_sha256(path: Path) -> str:
    """Stream-hash a file (used to dedupe re-indexing)."""

    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


# ── Per-source adapters ───────────────────────────────────────────────


def index_nwt_chapter(store: ConcordanceStore, chapter: NWTChapter) -> int:
    """Index one Bible chapter. Replaces previous entries for the same chapter."""

    entries = [
        IndexEntry(
            source_kind="nwt",
            source_id=chapter.source_id(),
            ref=chapter.ref_for(verse),
            chunk_text=text,
            language=chapter.language,
            url=chapter.url,
            source_path=None,
            source_sha256="",
        )
        for verse, text in chapter.verses
        if text and text.strip()
    ]
    return store.replace_source(
        source_kind="nwt",
        source_id=chapter.source_id(),
        entries=entries,
    )


def index_epub(store: ConcordanceStore, path: Path, *, language: str) -> int:
    """Index one EPUB file. Returns rows inserted; idempotent per-path."""

    sha = _file_sha256(path)
    if store.is_known_source("epub", str(path), sha):
        return 0
    pub = parse_epub(path)
    file_url = f"file://{path.resolve()}"
    entries: list[IndexEntry] = []
    for doc in pub.documents:
        for i, para in enumerate(doc.paragraphs):
            entries.append(
                IndexEntry(
                    source_kind="epub",
                    source_id=f"epub:{sha[:12]}:{doc.id}",
                    ref=f"{doc.id}:p{i}",
                    chunk_text=para,
                    language=language or pub.language or "en",
                    url=file_url,
                    source_path=str(path),
                    source_sha256=sha,
                )
            )
    n = store.add_many(entries)
    store.mark_source(
        source_kind="epub",
        source_path=str(path),
        source_sha256=sha,
        language=language,
        n_entries=n,
    )
    return n


def index_jwpub(store: ConcordanceStore, path: Path, *, language: str) -> int:
    """Index one JWPUB file (decrypted). Idempotent per (path, sha256)."""

    sha = _file_sha256(path)
    if store.is_known_source("jwpub", str(path), sha):
        return 0
    try:
        pub = parse_jwpub(path)
    except JwpubError:
        return 0
    file_url = f"file://{path.resolve()}"
    entries: list[IndexEntry] = []
    for doc in pub.documents:
        for i, para in enumerate(doc.paragraphs):
            entries.append(
                IndexEntry(
                    source_kind="jwpub",
                    source_id=f"jwpub:{pub.symbol}:{doc.document_id}",
                    ref=f"doc#{doc.document_id} p{i}",
                    chunk_text=para,
                    language=language,
                    url=file_url,
                    source_path=str(path),
                    source_sha256=sha,
                )
            )
    n = store.add_many(entries)
    store.mark_source(
        source_kind="jwpub",
        source_path=str(path),
        source_sha256=sha,
        language=language,
        n_entries=n,
    )
    return n


# ── Top-level dispatcher ──────────────────────────────────────────────


def build_index(
    paths: list[Path] | None = None,
    *,
    language: str,
    source_tag: str = "",  # reserved, currently informational only
    db_path: Path | None = None,
    force: bool = False,
    nwt_chapters: list[NWTChapter] | None = None,
) -> int:
    """Index a mix of files (.jwpub / .epub) and NWT chapters.

    Returns the total number of new rows inserted across all sources.
    Files with an unchanged sha256 are skipped unless `force=True`.
    """

    total = 0
    store = ConcordanceStore(db_path=db_path)
    try:
        for chapter in nwt_chapters or []:
            total += index_nwt_chapter(store, chapter)

        for p in paths or []:
            p = Path(p)
            if force and p.suffix.lower() in {".epub", ".jwpub"}:
                # Drop both the dedupe row and the existing entries so the next
                # call re-indexes from scratch.
                store._conn.execute(
                    "DELETE FROM concordance_sources WHERE source_path = ?",
                    (str(p),),
                )
                kind = "epub" if p.suffix.lower() == ".epub" else "jwpub"
                store._conn.execute(
                    "DELETE FROM concordance_entries WHERE source_path = ? AND source_kind = ?",
                    (str(p), kind),
                )

            if p.suffix.lower() == ".epub":
                total += index_epub(store, p, language=language)
            elif p.suffix.lower() == ".jwpub":
                total += index_jwpub(store, p, language=language)
            # silently ignore anything else — callers validate at the CLI layer
    finally:
        store.close()
    return total
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest packages/jw-core/tests/test_concordance_indexer.py -v`
Expected: 7 passed.

- [ ] **Step 6: Commit**

```bash
git add packages/jw-core/src/jw_core/concordance/indexer.py packages/jw-core/tests/test_concordance_indexer.py packages/jw-core/tests/fixtures/concordance/__init__.py
git commit -m "feat(concordance): indexer adapters for NWT/JWPUB/EPUB with sha256 dedupe"
```

---

### Task 4: Search API + snippet rendering

**Files:**
- Create: `packages/jw-core/src/jw_core/concordance/search.py`
- Create: `packages/jw-core/tests/test_concordance_search.py`
- Modify: `packages/jw-core/src/jw_core/concordance/__init__.py` (re-enable full re-exports)

- [ ] **Step 1: Write the failing test**

```python
# packages/jw-core/tests/test_concordance_search.py
"""Tests for jw_core.concordance.search — phrase, AND/OR, snippet markers."""

from __future__ import annotations

from pathlib import Path

import pytest

from jw_core.concordance.indexer import NWTChapter, build_index, index_nwt_chapter
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/jw-core/tests/test_concordance_search.py -v`
Expected: FAIL — search module missing.

- [ ] **Step 3: Implement the search API**

```python
# packages/jw-core/src/jw_core/concordance/search.py
"""Search API over the FTS5 concordance index.

Supports the native FTS5 query grammar: phrase ("..."), AND/OR/NOT,
prefix (foo*), and NEAR/N proximity. Regex is **not** supported — the
goal is deterministic literal/lexical matching, not pattern expansion.

The snippet renderer marks the matched span with the Unicode delimiters
`SNIPPET_START` (`‹`) and `SNIPPET_END` (`›`) so the output is Markdown
and HTML safe by default.
"""

from __future__ import annotations

import re
from pathlib import Path

from jw_core.concordance.models import ConcordanceHit
from jw_core.concordance.store import ConcordanceStore

SNIPPET_START = "‹"
SNIPPET_END = "›"
_REGEX_RED_FLAGS = re.compile(r"\\b|\\d|\\s|\\w|\[|\]|\{|\}|\+\B|\^|\$")


# ── Query helpers ──────────────────────────────────────────────────────


def escape_fts_phrase(text: str) -> str:
    """Quote `text` for use as an FTS5 phrase ("..."), doubling inner quotes."""

    return '"' + text.replace('"', '""') + '"'


def is_safe_query(query: str) -> bool:
    """Reject queries that look like regex (we're not a regex engine)."""

    return _REGEX_RED_FLAGS.search(query) is None


# ── Search ─────────────────────────────────────────────────────────────


def concordance_search(
    query: str,
    *,
    language: str | None = None,
    source_kind: str | None = None,
    max_results: int = 100,
    db_path: Path | None = None,
) -> list[ConcordanceHit]:
    """Run a literal FTS5 search and return hits sorted by FTS rank."""

    if not query.strip():
        return []
    if not is_safe_query(query):
        raise ValueError(
            "concordance_search does not support regex metacharacters. "
            "Use phrases (\"...\") and AND/OR/NEAR instead."
        )

    sql = [
        "SELECT e.entry_id, e.source_kind, e.source_id, e.ref, e.language, e.url, "
        "snippet(concordance_fts, 0, ?, ?, '…', 8) AS snip "
        "FROM concordance_fts f JOIN concordance_entries e ON e.entry_id = f.rowid "
        "WHERE concordance_fts MATCH ?",
    ]
    params: list[object] = [SNIPPET_START, SNIPPET_END, query]
    if language:
        sql.append("AND e.language = ?")
        params.append(language)
    if source_kind:
        sql.append("AND e.source_kind = ?")
        params.append(source_kind)
    sql.append("ORDER BY rank LIMIT ?")
    params.append(int(max_results))

    store = ConcordanceStore(db_path=db_path)
    try:
        rows = store._conn.execute(" ".join(sql), params).fetchall()
    finally:
        store.close()

    return [
        ConcordanceHit(
            entry_id=row["entry_id"],
            source_kind=row["source_kind"],
            source_id=row["source_id"],
            ref=row["ref"],
            snippet=row["snip"],
            language=row["language"],
            url=row["url"],
        )
        for row in rows
    ]
```

- [ ] **Step 4: Re-enable full re-exports in `__init__.py`**

```python
# packages/jw-core/src/jw_core/concordance/__init__.py
"""Exact-match concordance over the local decrypted JW corpus.

Public API:
    from jw_core.concordance import (
        build_index,
        concordance_search,
        ConcordanceHit,
        IndexEntry,
        ConcordanceStore,
        default_db_path,
    )

See `docs/superpowers/specs/2026-05-30-fase-28-concordance-design.md`.
"""

from jw_core.concordance.indexer import NWTChapter, build_index
from jw_core.concordance.models import ConcordanceHit, IndexEntry
from jw_core.concordance.search import concordance_search, escape_fts_phrase
from jw_core.concordance.store import ConcordanceStore, default_db_path

__all__ = [
    "ConcordanceHit",
    "ConcordanceStore",
    "IndexEntry",
    "NWTChapter",
    "build_index",
    "concordance_search",
    "default_db_path",
    "escape_fts_phrase",
]
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest packages/jw-core/tests/test_concordance_search.py -v`
Expected: 10 passed.

- [ ] **Step 6: Commit**

```bash
git add packages/jw-core/src/jw_core/concordance/search.py packages/jw-core/src/jw_core/concordance/__init__.py packages/jw-core/tests/test_concordance_search.py
git commit -m "feat(concordance): FTS5 search API with snippet markers and safety check"
```

---

### Task 5: CLI command `jw grep`

**Files:**
- Create: `packages/jw-cli/src/jw_cli/commands/grep.py`
- Modify: `packages/jw-cli/src/jw_cli/main.py`
- Modify: `packages/jw-cli/src/jw_cli/commands/__init__.py`
- Create: `packages/jw-cli/tests/test_grep_cmd.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/jw-cli/tests/test_grep_cmd.py
"""Tests for the `jw grep` CLI command."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from jw_cli.main import app
from tests.fixtures.concordance import build_minimal_epub  # type: ignore[import-not-found]

runner = CliRunner()


def test_grep_build_index_then_search(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("JW_CONCORDANCE_DB", str(tmp_path / "c.db"))
    epub = build_minimal_epub(
        tmp_path / "demo.epub",
        title="Demo",
        paragraphs=["the quick brown fox jumps over the lazy dog"],
    )
    r1 = runner.invoke(app, ["grep", "--build-index", str(epub), "--language", "en"])
    assert r1.exit_code == 0, r1.stdout
    assert "Indexed" in r1.stdout or "inserted" in r1.stdout.lower()

    r2 = runner.invoke(app, ["grep", "brown fox", "--language", "en"])
    assert r2.exit_code == 0, r2.stdout
    assert "‹brown fox›" in r2.stdout or "brown fox" in r2.stdout


def test_grep_stats(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("JW_CONCORDANCE_DB", str(tmp_path / "c.db"))
    r = runner.invoke(app, ["grep", "--stats"])
    assert r.exit_code == 0
    assert "total" in r.stdout.lower() or "empty" in r.stdout.lower()


def test_grep_rejects_regex(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("JW_CONCORDANCE_DB", str(tmp_path / "c.db"))
    r = runner.invoke(app, ["grep", r"\bword\b"])
    assert r.exit_code != 0
    assert "regex" in r.stdout.lower() or "support" in r.stdout.lower()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/jw-cli/tests/test_grep_cmd.py -v`
Expected: FAIL — `grep` command not registered.

- [ ] **Step 3: Implement the CLI command**

```python
# packages/jw-cli/src/jw_cli/commands/grep.py
"""`jw grep` — literal concordance search over the local index.

Usage:
    jw grep "<phrase>"                      # search
    jw grep "<phrase>" --language es        # filter by language
    jw grep --build-index file.jwpub        # add one publication
    jw grep --build-index ~/lib --recursive # add every .epub/.jwpub under dir
    jw grep --stats                         # show index stats
"""

from __future__ import annotations

from pathlib import Path

import typer
from jw_core.concordance import (
    ConcordanceStore,
    build_index,
    concordance_search,
    default_db_path,
)
from jw_core.concordance.search import is_safe_query
from rich.console import Console
from rich.table import Table

console = Console()


def _expand_paths(paths: list[Path], recursive: bool) -> list[Path]:
    out: list[Path] = []
    for p in paths:
        if p.is_dir():
            patterns = ("**/*.epub", "**/*.jwpub") if recursive else ("*.epub", "*.jwpub")
            for pattern in patterns:
                out.extend(sorted(p.glob(pattern)))
        elif p.suffix.lower() in {".epub", ".jwpub"}:
            out.append(p)
    return out


def grep_cmd(
    query: str = typer.Argument("", help="FTS5 query — use \"...\" for phrases"),
    language: str | None = typer.Option(None, "--language", "-l", help="ISO code (en/es/pt/...)"),
    source_kind: str | None = typer.Option(None, "--kind", help="'nwt' | 'jwpub' | 'epub'"),
    max_results: int = typer.Option(50, "--max", "-n", help="Cap result count"),
    build_index_paths: list[Path] = typer.Option(
        [],
        "--build-index",
        help="Path(s) to .epub/.jwpub or directories to ingest before searching",
        exists=False,
    ),
    recursive: bool = typer.Option(False, "--recursive", "-r", help="Scan directories recursively"),
    force: bool = typer.Option(False, "--force", help="Re-index even if sha256 unchanged"),
    stats: bool = typer.Option(False, "--stats", help="Print index stats and exit"),
) -> None:
    """Exact-match concordance over the local corpus."""

    db = default_db_path()

    if stats:
        store = ConcordanceStore(db_path=db)
        try:
            counts = store.stats()
            total = store.count()
        finally:
            store.close()
        if not total:
            console.print("[yellow]Concordance index is empty[/yellow]")
            return
        table = Table(title=f"Concordance index ({db})")
        table.add_column("source_kind")
        table.add_column("entries", justify="right")
        for k, n in sorted(counts.items()):
            table.add_row(k, str(n))
        table.add_row("[bold]total[/bold]", f"[bold]{total}[/bold]")
        console.print(table)
        return

    if build_index_paths:
        if not language:
            console.print("[red]--build-index requires --language[/red]")
            raise typer.Exit(code=2)
        files = _expand_paths(build_index_paths, recursive=recursive)
        if not files:
            console.print("[yellow]No .epub/.jwpub files found in given paths[/yellow]")
        n = build_index(paths=files, language=language, db_path=db, force=force)
        console.print(f"[green]Indexed[/green] {len(files)} file(s) → {n} new entry(ies)")
        if not query:
            return

    if not query:
        console.print("[yellow]Nothing to do — pass a query or --build-index or --stats[/yellow]")
        raise typer.Exit(code=2)

    if not is_safe_query(query):
        console.print(
            "[red]Regex metacharacters detected.[/red] "
            "This command supports FTS5 syntax (phrases, AND/OR/NEAR) — not regex."
        )
        raise typer.Exit(code=2)

    hits = concordance_search(
        query,
        language=language,
        source_kind=source_kind,
        max_results=max_results,
        db_path=db,
    )

    if not hits:
        console.print("[yellow]No matches[/yellow]")
        return

    table = Table(show_lines=False)
    table.add_column("#", justify="right", style="cyan", no_wrap=True)
    table.add_column("source", style="magenta", no_wrap=True)
    table.add_column("ref", no_wrap=True)
    table.add_column("snippet")
    for i, h in enumerate(hits, start=1):
        table.add_row(str(i), h.source_kind, h.ref, h.snippet)
    console.print(table)

    # Print URL footnotes if available.
    for i, h in enumerate(hits, start=1):
        if h.url:
            console.print(f"  [{i}] {h.url}", style="dim")
```

- [ ] **Step 4: Register the command**

Edit `packages/jw-cli/src/jw_cli/commands/__init__.py` — append:

```python
from jw_cli.commands.grep import grep_cmd
```

and include `grep_cmd` in the `__all__` list (matching the file's existing pattern).

Edit `packages/jw-cli/src/jw_cli/main.py` — wherever existing commands are registered (e.g. `app.command(...)(jwpub_cmd)`), add a matching line:

```python
from jw_cli.commands.grep import grep_cmd

app.command(name="grep", help="Literal concordance search over the local corpus.")(grep_cmd)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest packages/jw-cli/tests/test_grep_cmd.py -v`
Expected: 3 passed.

- [ ] **Step 6: Commit**

```bash
git add packages/jw-cli/src/jw_cli/commands/grep.py packages/jw-cli/src/jw_cli/commands/__init__.py packages/jw-cli/src/jw_cli/main.py packages/jw-cli/tests/test_grep_cmd.py
git commit -m "feat(cli): add `jw grep` command for exact concordance"
```

---

### Task 6: MCP tools — `concordance_build_index` and `concordance_search`

**Files:**
- Create: `packages/jw-mcp/src/jw_mcp/tools/concordance.py`
- Modify: `packages/jw-mcp/src/jw_mcp/server.py`
- Create: `packages/jw-mcp/tests/test_concordance_tools.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/jw-mcp/tests/test_concordance_tools.py
"""Tests for the concordance MCP tools."""

from __future__ import annotations

from pathlib import Path

import pytest

from jw_mcp.tools.concordance import concordance_build_index_tool, concordance_search_tool
from tests.fixtures.concordance import build_minimal_epub  # type: ignore[import-not-found]


def test_build_index_tool_returns_count(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JW_CONCORDANCE_DB", str(tmp_path / "c.db"))
    epub = build_minimal_epub(
        tmp_path / "x.epub",
        title="Demo",
        paragraphs=["one line", "another"],
    )
    out = concordance_build_index_tool(paths=[str(epub)], language="en")
    assert out["inserted"] == 2
    assert "error" not in out


def test_search_tool_returns_hits(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JW_CONCORDANCE_DB", str(tmp_path / "c.db"))
    epub = build_minimal_epub(
        tmp_path / "x.epub",
        title="Demo",
        paragraphs=["the kingdom of God is at hand"],
    )
    concordance_build_index_tool(paths=[str(epub)], language="en")
    hits = concordance_search_tool(query='"kingdom of God"', language="en", max_results=10)
    assert hits["hits"]
    assert hits["hits"][0]["ref"]


def test_search_tool_rejects_regex(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JW_CONCORDANCE_DB", str(tmp_path / "c.db"))
    out = concordance_search_tool(query=r"\bx\b")
    assert "error" in out
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/jw-mcp/tests/test_concordance_tools.py -v`
Expected: FAIL — `tools.concordance` missing.

- [ ] **Step 3: Implement the MCP tools**

```python
# packages/jw-mcp/src/jw_mcp/tools/concordance.py
"""MCP tool wrappers for the concordance module.

Both tools degrade gracefully: any RuntimeError / ValueError from the
underlying API is captured and returned as `{"error": "..."}` so the MCP
session survives transient failures.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from jw_core.concordance import build_index, concordance_search


def concordance_build_index_tool(
    paths: list[str],
    language: str,
    force: bool = False,
) -> dict[str, Any]:
    """Ingest .epub / .jwpub files into the concordance index.

    Args:
        paths: list of file paths (NOT directories — expand at the caller).
        language: ISO code (en/es/pt/...).
        force: re-index even if the sha256 has not changed.

    Returns:
        {"inserted": int, "files": int} on success, {"error": "..."} on failure.
    """

    try:
        file_paths = [Path(p) for p in paths]
        n = build_index(paths=file_paths, language=language, force=force)
        return {"inserted": n, "files": len(file_paths)}
    except (RuntimeError, ValueError, OSError) as exc:
        return {"error": str(exc)}


def concordance_search_tool(
    query: str,
    language: str | None = None,
    source_kind: str | None = None,
    max_results: int = 50,
) -> dict[str, Any]:
    """Run a literal FTS5 search and return hits.

    Args:
        query: FTS5 syntax — phrase ("..."), AND/OR/NEAR. NOT regex.
        language: optional ISO code filter.
        source_kind: 'nwt' | 'jwpub' | 'epub' to scope the search.
        max_results: cap (default 50, hard-cap 500).

    Returns:
        {"hits": [{"source_kind", "ref", "snippet", "language", "url"}, ...]}
        or {"error": "..."}.
    """

    try:
        hits = concordance_search(
            query,
            language=language,
            source_kind=source_kind,
            max_results=min(int(max_results), 500),
        )
        return {
            "hits": [
                {
                    "entry_id": h.entry_id,
                    "source_kind": h.source_kind,
                    "source_id": h.source_id,
                    "ref": h.ref,
                    "snippet": h.snippet,
                    "language": h.language,
                    "url": h.url,
                }
                for h in hits
            ]
        }
    except (RuntimeError, ValueError) as exc:
        return {"error": str(exc)}
```

- [ ] **Step 4: Register on the MCP server**

Edit `packages/jw-mcp/src/jw_mcp/server.py` — locate the section where other tools are decorated with `@mcp.tool` and append:

```python
from jw_mcp.tools.concordance import (
    concordance_build_index_tool,
    concordance_search_tool,
)

mcp.tool(name="concordance_build_index")(concordance_build_index_tool)
mcp.tool(name="concordance_search")(concordance_search_tool)
```

If the file uses a list-based registration pattern, follow that convention instead. The test in Step 1 imports the functions directly, so registration is for runtime discovery only.

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest packages/jw-mcp/tests/test_concordance_tools.py -v`
Expected: 3 passed.

- [ ] **Step 6: Commit**

```bash
git add packages/jw-mcp/src/jw_mcp/tools/concordance.py packages/jw-mcp/src/jw_mcp/server.py packages/jw-mcp/tests/test_concordance_tools.py
git commit -m "feat(mcp): expose concordance_build_index and concordance_search tools"
```

---

### Task 7: NWT chapter ingestion helper for CLI

**Files:**
- Modify: `packages/jw-cli/src/jw_cli/commands/grep.py` — add `--build-nwt` option.
- Create: `packages/jw-core/src/jw_core/concordance/nwt_ingest.py` — pure-CPU verse extractor that takes WOL HTML and returns `NWTChapter`. The actual fetch lives in the CLI (so this module stays network-free).

- [ ] **Step 1: Write the failing test**

```python
# packages/jw-core/tests/test_concordance_nwt_ingest.py
"""Tests for the NWT chapter HTML extractor."""

from __future__ import annotations

from jw_core.concordance.nwt_ingest import nwt_chapter_from_html


_HTML_FIXTURE = """
<div id="bibleText">
  <span id="v43003015" class="v">
    <sup class="vsNum">15</sup>
    Para que todo el que ejerce fe en él tenga vida eterna.
  </span>
  <span id="v43003016" class="v">
    <sup class="vsNum">16</sup>
    Porque tanto amó Dios al mundo que dio a su Hijo unigénito.
  </span>
</div>
"""


def test_nwt_chapter_from_html_extracts_verses() -> None:
    chapter = nwt_chapter_from_html(
        _HTML_FIXTURE,
        language="es",
        book_num=43,
        chapter=3,
        url="https://wol.jw.org/es/wol/b/r4/lp-s/nwt/E/2024/43/3",
        book_name="Juan",
    )
    assert chapter.book_num == 43
    assert chapter.chapter == 3
    assert len(chapter.verses) == 2
    assert chapter.verses[0][0] == 15
    assert "ejerce fe" in chapter.verses[0][1]
    assert chapter.source_id() == "nwt:es:43:3"


def test_nwt_chapter_from_html_handles_empty() -> None:
    chapter = nwt_chapter_from_html(
        "<div></div>",
        language="en",
        book_num=1,
        chapter=1,
    )
    assert chapter.verses == []
```

- [ ] **Step 2: Implement the extractor**

```python
# packages/jw-core/src/jw_core/concordance/nwt_ingest.py
"""Extract verse-keyed text from a WOL Bible chapter HTML page.

WOL renders each verse as `<span id="v{book:03}{chapter:03}{verse:03}" ...>`
with a `<sup class="vsNum">` prefix carrying the verse number. We strip the
sup and keep the trailing text. Anything else (footnote markers, cross-ref
boxes) is dropped.
"""

from __future__ import annotations

import re

from bs4 import BeautifulSoup

from jw_core.concordance.indexer import NWTChapter

_VERSE_ID_RE = re.compile(r"^v(\d{2})(\d{3})(\d{3})$")


def nwt_chapter_from_html(
    html: str,
    *,
    language: str,
    book_num: int,
    chapter: int,
    url: str | None = None,
    book_name: str = "",
    publication: str = "nwt",
) -> NWTChapter:
    """Parse the chapter HTML and return an `NWTChapter` ready to index."""

    soup = BeautifulSoup(html, "lxml")
    verses: list[tuple[int, str]] = []
    for span in soup.find_all("span", id=_VERSE_ID_RE):
        # Drop the verse-number <sup>, footnote markers, and cross-ref links
        for junk in span.find_all(["sup", "a"], class_=["vsNum", "fn", "xref"]):
            junk.decompose()
        # Some content is wrapped in <p> children — keep the readable text.
        text = span.get_text(" ", strip=True)
        text = re.sub(r"\s+", " ", text).strip()
        if not text:
            continue
        verse_num = int(span["id"][-3:])  # last 3 digits are the verse
        verses.append((verse_num, text))

    return NWTChapter(
        language=language,
        book_num=book_num,
        chapter=chapter,
        verses=verses,
        url=url,
        book_name=book_name,
        publication=publication,
    )
```

- [ ] **Step 3: Run test to verify it passes**

Run: `uv run pytest packages/jw-core/tests/test_concordance_nwt_ingest.py -v`
Expected: 2 passed.

- [ ] **Step 4: Wire `--build-nwt` into the CLI**

Modify `packages/jw-cli/src/jw_cli/commands/grep.py`:

Add option:

```python
build_nwt: list[str] = typer.Option(
    [],
    "--build-nwt",
    help="Reference(s) like 'Juan 3' or '43:3' to fetch from WOL and index.",
)
```

And handle it inside `grep_cmd` before the search step:

```python
if build_nwt:
    if not language:
        console.print("[red]--build-nwt requires --language[/red]")
        raise typer.Exit(code=2)
    import asyncio
    from jw_core.clients.factory import build_clients
    from jw_core.concordance import build_index
    from jw_core.concordance.nwt_ingest import nwt_chapter_from_html
    from jw_core.parsers.reference import parse_reference

    async def _ingest_nwt() -> list:
        chapters = []
        clients = build_clients()
        try:
            for raw in build_nwt:
                parsed = parse_reference(raw, language=language)
                if not parsed:
                    console.print(f"[yellow]Could not parse '{raw}' — skipping[/yellow]")
                    continue
                url, html = await clients.wol.get_bible_chapter(
                    parsed.book_num, parsed.chapter, language=language
                )
                chapters.append(
                    nwt_chapter_from_html(
                        html,
                        language=language,
                        book_num=parsed.book_num,
                        chapter=parsed.chapter,
                        url=url,
                        book_name=parsed.book_name,
                    )
                )
        finally:
            await clients.aclose()
        return chapters

    chapters = asyncio.run(_ingest_nwt())
    n_nwt = build_index(paths=None, language=language, db_path=db, nwt_chapters=chapters)
    console.print(f"[green]NWT[/green] {len(chapters)} chapter(s) → {n_nwt} verse(s)")
```

Note: the exact import paths above (`build_clients`, `parse_reference`) must match what the workspace already exposes; if signatures differ, adapt the call but keep the structure.

- [ ] **Step 5: Commit**

```bash
git add packages/jw-core/src/jw_core/concordance/nwt_ingest.py packages/jw-core/tests/test_concordance_nwt_ingest.py packages/jw-cli/src/jw_cli/commands/grep.py
git commit -m "feat(concordance): NWT chapter HTML extractor + --build-nwt CLI option"
```

---

### Task 8: Property-based test — large random corpus stays consistent

**Files:**
- Create: `packages/jw-core/tests/test_concordance_property.py`

- [ ] **Step 1: Write the property test**

```python
# packages/jw-core/tests/test_concordance_property.py
"""Property-based smoke test for the concordance store.

Inserting N random unique sentences and searching for one of their tokens
should always return a non-empty result; inserting then deleting must
return the store to count=0.
"""

from __future__ import annotations

import random
import string
from pathlib import Path

import pytest

from jw_core.concordance.indexer import NWTChapter, index_nwt_chapter
from jw_core.concordance.search import concordance_search
from jw_core.concordance.store import ConcordanceStore


def _random_sentence(rng: random.Random) -> str:
    return " ".join(
        "".join(rng.choices(string.ascii_lowercase, k=rng.randint(3, 8)))
        for _ in range(rng.randint(5, 10))
    )


@pytest.mark.parametrize("seed", [0, 1, 7, 42, 100])
def test_random_corpus_search_finds_every_inserted_token(tmp_path: Path, seed: int) -> None:
    rng = random.Random(seed)
    db = tmp_path / f"c-{seed}.db"
    store = ConcordanceStore(db_path=db)
    try:
        verses: list[tuple[int, str]] = []
        sample_tokens: list[str] = []
        for i in range(1, 51):
            s = _random_sentence(rng)
            verses.append((i, s))
            sample_tokens.append(s.split()[0])
        chapter = NWTChapter(
            language="en",
            book_num=99,
            chapter=1,
            verses=verses,
            url=None,
        )
        index_nwt_chapter(store, chapter)
    finally:
        store.close()

    for tok in sample_tokens[:10]:
        hits = concordance_search(tok, db_path=db, max_results=100)
        assert any(tok in h.snippet for h in hits), (
            f"token {tok!r} should appear in at least one hit for seed={seed}"
        )
```

- [ ] **Step 2: Run test to verify it passes**

Run: `uv run pytest packages/jw-core/tests/test_concordance_property.py -v`
Expected: 5 passed.

- [ ] **Step 3: Commit**

```bash
git add packages/jw-core/tests/test_concordance_property.py
git commit -m "test(concordance): property-based smoke for 50-verse random corpora"
```

---

### Task 9: Documentation — `docs/guias/concordancia-exacta.md`

**Files:**
- Create: `docs/guias/concordancia-exacta.md`
- Modify: `docs/README.md` — link the new guide.

- [ ] **Step 1: Write the user-facing guide**

```markdown
# Concordancia exacta NWT + publicaciones

> Búsqueda **literal** sobre tu corpus local descifrado (NWT, JWPUB, EPUB). Complementa el RAG semántico — no lo reemplaza.

## Cuándo usar concordancia y cuándo RAG

| Pregunta | Herramienta |
|---|---|
| ¿Dónde aparece exactamente la frase "conocimiento exacto"? | `jw grep "\"conocimiento exacto\""` |
| ¿Qué versículos hablan sobre el conocimiento? | `jw rag "qué dice la Biblia sobre el conocimiento"` |
| ¿Cuántas veces aparece "Jehová" en el NT? | `jw grep "Jehová" --kind nwt --max 500` |

## Construir el índice

```bash
# Indexar un archivo concreto
jw grep --build-index ~/jw-publications/w24.jwpub --language es

# Indexar una carpeta entera (recursivo)
jw grep --build-index ~/jw-publications --language es --recursive

# Ingerir un capítulo NWT desde WOL (red sólo en este paso)
jw grep --build-nwt "Juan 3" --language es

# Forzar re-indexación de un archivo modificado
jw grep --build-index w24.jwpub --language es --force

# Ver estadísticas
jw grep --stats
```

El índice vive en `~/.jw-agent-toolkit/concordance.db` (override con `JW_CONCORDANCE_DB`). Es SQLite WAL — abierto en lectura por múltiples procesos sin bloqueo.

## Gramática de consultas

Soporta la sintaxis nativa **FTS5** (no regex):

| Operador | Ejemplo | Significado |
|---|---|---|
| Phrase | `"reino de Dios"` | Frase exacta |
| AND | `Jehová amor` | Ambos términos (orden libre) |
| OR | `"reino de Dios" OR "reino del cielo"` | Cualquiera |
| NOT | `Jehová NOT espíritu` | Excluir |
| NEAR | `Jehová NEAR/3 amor` | Distancia ≤ 3 tokens |
| Prefix | `inteli*` | "inteligente", "inteligencia"... |

### Diacríticos

El tokenizador es `unicode61 remove_diacritics 2` → **busca `"espiritu"` y encuentras `"Espíritu"`** (y viceversa). Esto vale en español/portugués/inglés. Si necesitas búsqueda sensible a acentos, abre un issue.

### Sin regex

`\b`, `[abc]`, `+`, `^`, `$` y compañía **no** funcionan — el comando se rehúsa con un mensaje claro. Para variantes morfológicas usa el RAG semántico.

## Filtros

```bash
jw grep "amó" --language es
jw grep "amó" --kind nwt          # sólo Biblia
jw grep "amó" --kind jwpub        # sólo publicaciones
jw grep "amó" --max 200           # techo de resultados
```

## API Python

```python
from jw_core.concordance import build_index, concordance_search
from pathlib import Path

build_index(
    paths=[Path("~/jw-publications/w24.jwpub").expanduser()],
    language="es",
)
hits = concordance_search('"conocimiento exacto"', language="es")
for h in hits:
    print(h.ref, "→", h.snippet, "·", h.url or "(sin URL canónica)")
```

## MCP tools

- `concordance_build_index(paths, language, force)` → `{inserted, files}` ó `{error}`.
- `concordance_search(query, language?, source_kind?, max_results?)` → `{hits: [...]}` ó `{error}`.

## Limitaciones conocidas

- No indexa fuentes Obsidian (Fase 20) — pendiente.
- No persiste el contexto antes/después del párrafo — sólo el párrafo en sí. Si quieres más contexto, abre el `url` en navegador.
- El tamaño del índice crece linealmente con el corpus. ~50 MB cada 25 publicaciones.

## Privacidad y copyright

La DB queda **sólo en tu máquina**. Nada se sube. Las publicaciones siguen siendo propiedad de Watch Tower Bible and Tract Society — el toolkit solo facilita búsqueda offline sobre el material que ya tienes legalmente descargado.
```

- [ ] **Step 2: Link from `docs/README.md`** (under the guides section).

- [ ] **Step 3: Commit**

```bash
git add docs/guias/concordancia-exacta.md docs/README.md
git commit -m "docs(concordance): user guide for jw grep"
```

---

### Task 10: Roadmap + Vision Audit updates

**Files:**
- Modify: `docs/ROADMAP.md`
- Modify: `docs/VISION_AUDIT.md`

- [ ] **Step 1: Append the Fase 28 section to `docs/ROADMAP.md`** under the existing Tier-3 group:

```markdown
### Fase 28 — Concordancia exacta NWT + publicaciones ✅

- `jw_core.concordance` con SQLite FTS5 y dedupe por sha256.
- Indexer adapters: NWT chapters (HTML), JWPUB descifrado, EPUB.
- CLI `jw grep "<phrase>"` con `--build-index`, `--build-nwt`, `--stats`, `--kind`, `--language`.
- MCP tools `concordance_build_index` y `concordance_search`.
- Guía: [`docs/guias/concordancia-exacta.md`](guias/concordancia-exacta.md).
```

- [ ] **Step 2: Update `docs/VISION_AUDIT.md`** — mark item #7 (concordance) as covered with link to spec + guide.

- [ ] **Step 3: Commit**

```bash
git add docs/ROADMAP.md docs/VISION_AUDIT.md
git commit -m "docs: mark Fase 28 (concordance) as shipped"
```

---

### Task 11: Eval — add 3 Golden Cases for Fase 28 (Fase 22 policy)

**Files:**
- Create: `packages/jw-eval/fixtures/golden_qa/l1/concordance_phrase_es.yaml`
- Create: `packages/jw-eval/fixtures/golden_qa/l1/concordance_snippet_markers_en.yaml`
- Create: `packages/jw-eval/fixtures/golden_qa/l2/concordance_nwt_url_es.yaml`

- [ ] **Step 1: Add the L1 phrase case**

```yaml
# packages/jw-eval/fixtures/golden_qa/l1/concordance_phrase_es.yaml
id: l1_concordance_phrase_es
agent: concordance_search
layer: l1
input:
  query: '"conocimiento exacto"'
  language: es
expected:
  min_findings: 1
  must_have_citation: false  # snippet OK without URL when corpus is jwpub
metadata:
  topic: concordance.phrase_search
  added_at: 2026-05-30
```

- [ ] **Step 2: Add the L1 snippet-marker case**

```yaml
# packages/jw-eval/fixtures/golden_qa/l1/concordance_snippet_markers_en.yaml
id: l1_concordance_snippet_markers_en
agent: concordance_search
layer: l1
input:
  query: '"kingdom of God"'
  language: en
expected:
  min_findings: 1
  forbidden_keywords_in_findings:
    - "<mark>"  # we use ‹…› not HTML
metadata:
  topic: concordance.snippet
  added_at: 2026-05-30
```

- [ ] **Step 3: Add the L2 NWT URL case**

```yaml
# packages/jw-eval/fixtures/golden_qa/l2/concordance_nwt_url_es.yaml
id: l2_concordance_nwt_url_es
agent: concordance_search
layer: l2
input:
  query: '"amó tanto al mundo"'
  language: es
expected:
  expected_citations:
    - https://wol.jw.org/es/wol/b/r4/lp-s/nwt/E/2024/43/3
  support_phrases:
    - "amó tanto al mundo"
metadata:
  topic: concordance.url_resolution
  added_at: 2026-05-30
```

The eval suite already treats `agent` as a registry key; Fase 22 must add a `concordance_search` adapter that wraps `concordance_search` with the GoldenCase input format. If that adapter is not yet wired, file a follow-up issue — the YAML lands now so coverage is reserved.

- [ ] **Step 4: Commit**

```bash
git add packages/jw-eval/fixtures/golden_qa/l1/concordance_*.yaml packages/jw-eval/fixtures/golden_qa/l2/concordance_*.yaml
git commit -m "feat(jw-eval): add 3 golden cases for Fase 28 (concordance)"
```

---

### Task 12: Final integration smoke

**Files:**
- None (manual + CI).

- [ ] **Step 1: Full test sweep**

```bash
.venv/bin/python -m pytest packages/jw-core/tests packages/jw-cli/tests packages/jw-mcp/tests -k "concordance" -v
```
Expected: all green.

- [ ] **Step 2: Manual smoke with a synthetic EPUB**

```bash
uv run python -c "
from pathlib import Path
from tests.fixtures.concordance import build_minimal_epub
build_minimal_epub(Path('/tmp/c.epub'), title='Demo', paragraphs=['the kingdom of God is at hand', 'jehovah is love'])
"
uv run jw grep --build-index /tmp/c.epub --language en
uv run jw grep '"kingdom of God"' --language en
uv run jw grep --stats
```

Expected: index builds, grep returns one hit with `‹kingdom of God›` markers, stats shows `epub: 2`.

- [ ] **Step 3: Verify full suite still passes (no regression)**

```bash
.venv/bin/python -m pytest packages/ -q
```
Expected: 551 + new tests, 0 failures.

- [ ] **Step 4: Commit final tidy-up if needed**

```bash
git status
# only commit if there are residual fixture deletions or docstring tweaks
```

---

## Self-review

**What I'm confident about**

- The schema is a near-clone of the proven `personal_notes` pattern (FTS5 + triggers + WAL) which already ships and passes property tests. Risk is low.
- The indexer separation (no I/O in `concordance`; HTML fetch lives in the CLI) keeps the module testable without network and matches the project's "no LLM/network in critical path" rule.
- TDD discipline is enforced — every task writes its failing test first, then implements.
- Diacritic-insensitive tokenizer is the right default for Spanish/Portuguese users; the trade-off is documented and reversible.

**What I'd watch in code review**

- Task 7's `--build-nwt` wiring depends on the exact `build_clients()` / `parse_reference` signatures. If those have drifted, the structure stays valid but the call site needs adjusting.
- Task 6 step 4 (MCP registration) assumes a specific decorator pattern — confirm with `packages/jw-mcp/src/jw_mcp/server.py` before edit.
- The L2 eval case (Task 11 step 3) ties to a real WOL URL whose HTML snapshot must exist; Fase 22's `scripts/build_eval_snapshots.py` covers this.
- `concordance_search`'s `is_safe_query` is intentionally conservative — false-positive rejections on legitimate FTS5 queries containing `^` (start anchor) are acceptable for v1.

**Open question for the human**

- Should `--build-nwt` accept an entire book (e.g. `--build-nwt Juan`) and loop over its chapters with throttling, or stay one-chapter-per-flag for v1? The plan implements one-per-flag. If you want book-level ingestion, that's a small Task 7.5.

## Execution choice

Recommended path:

1. Tasks 1–4 (core module): **sequential**, TDD strict.
2. Tasks 5–6 (CLI + MCP): can be done in **parallel** by two workers once Task 4 lands, because they don't touch each other's files.
3. Tasks 7–9: sequential after 5–6.
4. Tasks 10–12: sequential (docs + integration).

For an agent run, use `superpowers:subagent-driven-development` and dispatch Tasks 5 and 6 in parallel after Task 4's commit lands. Total wall time estimate: **2–3 days** with one engineer, **1–1.5 days** with two parallel agents.
