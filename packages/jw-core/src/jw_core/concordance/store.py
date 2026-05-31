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
