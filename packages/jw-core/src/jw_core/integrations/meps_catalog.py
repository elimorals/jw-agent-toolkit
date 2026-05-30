"""Local MEPS docid ↔ publication-symbol catalog.

The official `jwlibrary://` URL scheme takes either a Bible address or a
`docid=N` pointing at a MEPS document. Watch Tower does not publish a
mapping from publication symbol ("w24", "bh", "lff") to MEPS document
ids, so we derive it locally by indexing the user's downloaded `.jwpub`
files (already decrypted via `jw_core.parsers.jwpub`).

Once populated, the catalog answers two key questions:

  1. "Given a publication symbol (and optional chapter), what's the MEPS
     `document_id` I should pass to `build_publication_url`?"
  2. "Given a `document_id`, which publication does it belong to?"

Storage: a small SQLite file (default `~/.jw-agent-toolkit/meps_catalog.db`).
All writes happen via `index_jwpub`; reads go through the lookup helpers.

Multiple language versions of the same publication coexist — `MepsLanguage`
disambiguates. Re-indexing the same `.jwpub` is idempotent (we upsert on
(pub_code, language_index, document_id)).
"""

from __future__ import annotations

import logging
import os
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

from jw_core.parsers.jwpub import parse_jwpub_metadata

logger = logging.getLogger(__name__)

__all__ = [
    "CatalogDocument",
    "CatalogPublication",
    "MepsCatalog",
    "default_catalog_path",
    "index_jwpub",
]

_DEFAULT_PATH_ENV = "JW_MEPS_CATALOG_PATH"
_DEFAULT_PATH = Path("~/.jw-agent-toolkit/meps_catalog.db").expanduser()

_SCHEMA = """
CREATE TABLE IF NOT EXISTS publication (
    pub_code TEXT NOT NULL,
    language_index INTEGER NOT NULL DEFAULT 0,
    title TEXT NOT NULL DEFAULT '',
    short_title TEXT NOT NULL DEFAULT '',
    year INTEGER,
    publication_type TEXT NOT NULL DEFAULT '',
    source_path TEXT NOT NULL DEFAULT '',
    last_indexed_at TEXT NOT NULL DEFAULT '',
    PRIMARY KEY (pub_code, language_index)
);
CREATE TABLE IF NOT EXISTS document (
    document_id INTEGER NOT NULL,
    meps_document_id INTEGER NOT NULL,
    pub_code TEXT NOT NULL,
    language_index INTEGER NOT NULL DEFAULT 0,
    title TEXT NOT NULL DEFAULT '',
    toc_title TEXT NOT NULL DEFAULT '',
    chapter_number INTEGER,
    section_number INTEGER NOT NULL DEFAULT 0,
    first_page_number INTEGER,
    last_page_number INTEGER,
    PRIMARY KEY (pub_code, language_index, document_id)
);
CREATE INDEX IF NOT EXISTS idx_document_meps ON document(meps_document_id);
CREATE INDEX IF NOT EXISTS idx_document_chapter ON document(pub_code, chapter_number);
"""


def default_catalog_path() -> Path:
    env = os.environ.get(_DEFAULT_PATH_ENV)
    return Path(env).expanduser() if env else _DEFAULT_PATH


@dataclass
class CatalogPublication:
    pub_code: str
    language_index: int
    title: str = ""
    short_title: str = ""
    year: int | None = None
    publication_type: str = ""
    source_path: str = ""
    last_indexed_at: str = ""

    def to_dict(self) -> dict:
        return self.__dict__.copy()


@dataclass
class CatalogDocument:
    document_id: int
    meps_document_id: int
    pub_code: str
    language_index: int
    title: str = ""
    toc_title: str = ""
    chapter_number: int | None = None
    section_number: int = 0
    first_page_number: int | None = None
    last_page_number: int | None = None

    def to_dict(self) -> dict:
        return self.__dict__.copy()


# ── Store ──────────────────────────────────────────────────────────────


class MepsCatalog:
    """SQLite-backed catalog of (pub_code, language) → documents.

    Use as a context manager when doing multiple operations:

        with MepsCatalog() as cat:
            cat.index_jwpub("/path/to/file.jwpub")
            docs = cat.find_documents(pub_code="bh")
    """

    def __init__(self, db_path: Path | str | None = None) -> None:
        self.path = Path(db_path).expanduser() if db_path else default_catalog_path()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn: sqlite3.Connection | None = None

    def __enter__(self) -> MepsCatalog:
        self._open()
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()

    def _open(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(self.path)
            self._conn.row_factory = sqlite3.Row
            self._conn.executescript(_SCHEMA)
        return self._conn

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    # ── Index ──────────────────────────────────────────────────────────

    def index_jwpub(self, jwpub_path: Path | str) -> dict:
        """Parse a `.jwpub` metadata block and upsert its publication + docs.

        Returns a small dict with `pub_code`, `language_index`, `documents`,
        `inserted_documents`, `updated_documents`.
        """
        meta = parse_jwpub_metadata(jwpub_path)
        if not meta.symbol:
            raise ValueError(f"JWPUB missing publication symbol: {jwpub_path!r}")
        conn = self._open()
        now = datetime.now(timezone.utc).isoformat()

        # Upsert publication row.
        conn.execute(
            """
            INSERT INTO publication
                (pub_code, language_index, title, short_title, year,
                 publication_type, source_path, last_indexed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(pub_code, language_index) DO UPDATE SET
                title = excluded.title,
                short_title = excluded.short_title,
                year = excluded.year,
                publication_type = excluded.publication_type,
                source_path = excluded.source_path,
                last_indexed_at = excluded.last_indexed_at
            """,
            (
                meta.symbol,
                meta.language_index,
                meta.title,
                meta.short_title,
                meta.year,
                meta.publication_type,
                str(jwpub_path),
                now,
            ),
        )

        # Upsert documents.
        inserted = 0
        updated = 0
        for doc in meta.documents:
            cur = conn.execute(
                """
                INSERT INTO document
                    (document_id, meps_document_id, pub_code, language_index,
                     title, toc_title, chapter_number, section_number,
                     first_page_number, last_page_number)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(pub_code, language_index, document_id) DO UPDATE SET
                    meps_document_id = excluded.meps_document_id,
                    title = excluded.title,
                    toc_title = excluded.toc_title,
                    chapter_number = excluded.chapter_number,
                    section_number = excluded.section_number,
                    first_page_number = excluded.first_page_number,
                    last_page_number = excluded.last_page_number
                """,
                (
                    doc.document_id,
                    doc.meps_document_id,
                    meta.symbol,
                    meta.language_index,
                    doc.title,
                    doc.toc_title,
                    doc.chapter_number,
                    doc.section_number,
                    doc.first_page_number,
                    doc.last_page_number,
                ),
            )
            if cur.rowcount == 1 and not _existed_before(conn, doc.document_id, meta.symbol, meta.language_index):
                inserted += 1
            else:
                updated += 1
        conn.commit()
        return {
            "pub_code": meta.symbol,
            "language_index": meta.language_index,
            "documents": len(meta.documents),
            "inserted_documents": inserted,
            "updated_documents": updated,
            "publication_title": meta.title,
        }

    # ── Lookups ────────────────────────────────────────────────────────

    def list_publications(
        self,
        *,
        pub_code: str | None = None,
        language_index: int | None = None,
    ) -> list[CatalogPublication]:
        conn = self._open()
        clauses: list[str] = []
        params: list = []
        if pub_code:
            clauses.append("pub_code = ?")
            params.append(pub_code)
        if language_index is not None:
            clauses.append("language_index = ?")
            params.append(language_index)
        where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        rows = conn.execute(
            f"SELECT * FROM publication{where} ORDER BY pub_code, language_index",
            params,
        ).fetchall()
        return [_pub_from_row(r) for r in rows]

    def find_documents(
        self,
        *,
        pub_code: str | None = None,
        document_id: int | None = None,
        meps_document_id: int | None = None,
        language_index: int | None = None,
        chapter_number: int | None = None,
        limit: int | None = None,
    ) -> list[CatalogDocument]:
        conn = self._open()
        clauses: list[str] = []
        params: list = []
        if pub_code:
            clauses.append("pub_code = ?")
            params.append(pub_code)
        if document_id is not None:
            clauses.append("document_id = ?")
            params.append(document_id)
        if meps_document_id is not None:
            clauses.append("meps_document_id = ?")
            params.append(meps_document_id)
        if language_index is not None:
            clauses.append("language_index = ?")
            params.append(language_index)
        if chapter_number is not None:
            clauses.append("chapter_number = ?")
            params.append(chapter_number)
        where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        limit_sql = f" LIMIT {int(limit)}" if limit else ""
        rows = conn.execute(
            f"SELECT * FROM document{where} ORDER BY pub_code, chapter_number, document_id{limit_sql}",
            params,
        ).fetchall()
        return [_doc_from_row(r) for r in rows]

    def resolve_docid(
        self,
        pub_code: str,
        *,
        chapter_number: int | None = None,
        language_index: int | None = None,
    ) -> CatalogDocument | None:
        """Pick the single best document for (pub_code, chapter, language).

        Selection rules:
          - When `chapter_number` is given, match it exactly.
          - When `language_index` is None, prefer English (index 0), else
            the first by language_index ascending.
          - Otherwise return the first document of the publication.
        """
        candidates = self.find_documents(
            pub_code=pub_code,
            chapter_number=chapter_number,
            language_index=language_index,
        )
        if not candidates:
            return None
        if language_index is not None:
            return candidates[0]
        # Prefer index 0 (English) when no language was specified.
        for c in candidates:
            if c.language_index == 0:
                return c
        return candidates[0]

    def stats(self) -> dict:
        conn = self._open()
        n_pubs = conn.execute("SELECT COUNT(*) FROM publication").fetchone()[0]
        n_docs = conn.execute("SELECT COUNT(*) FROM document").fetchone()[0]
        return {"db_path": str(self.path), "publications": n_pubs, "documents": n_docs}

    def __iter__(self) -> Iterator[CatalogPublication]:
        return iter(self.list_publications())


# ── Helpers ────────────────────────────────────────────────────────────


def index_jwpub(jwpub_path: Path | str, *, db_path: Path | str | None = None) -> dict:
    """Module-level shortcut for one-off indexing."""
    with MepsCatalog(db_path=db_path) as cat:
        return cat.index_jwpub(jwpub_path)


def _existed_before(
    conn: sqlite3.Connection,
    document_id: int,
    pub_code: str,
    language_index: int,
) -> bool:
    # Helper used during upsert to distinguish insert vs update. SQLite's
    # rowcount is 1 either way under `ON CONFLICT DO UPDATE`, so we check
    # against the count of rows with last_indexed_at older than now.
    row = conn.execute(
        "SELECT 1 FROM document WHERE pub_code=? AND language_index=? AND document_id=?",
        (pub_code, language_index, document_id),
    ).fetchone()
    return row is not None


def _pub_from_row(row: sqlite3.Row) -> CatalogPublication:
    return CatalogPublication(
        pub_code=row["pub_code"],
        language_index=int(row["language_index"]),
        title=row["title"] or "",
        short_title=row["short_title"] or "",
        year=row["year"],
        publication_type=row["publication_type"] or "",
        source_path=row["source_path"] or "",
        last_indexed_at=row["last_indexed_at"] or "",
    )


def _doc_from_row(row: sqlite3.Row) -> CatalogDocument:
    return CatalogDocument(
        document_id=int(row["document_id"]),
        meps_document_id=int(row["meps_document_id"]),
        pub_code=row["pub_code"],
        language_index=int(row["language_index"]),
        title=row["title"] or "",
        toc_title=row["toc_title"] or "",
        chapter_number=row["chapter_number"],
        section_number=int(row["section_number"] or 0),
        first_page_number=row["first_page_number"],
        last_page_number=row["last_page_number"],
    )
