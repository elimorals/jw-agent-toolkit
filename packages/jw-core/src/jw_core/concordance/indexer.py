"""Indexer adapters that turn NWT chapters / JWPUB / EPUB into IndexEntry rows.

The indexer is the only place that touches the disk parsers; the store
stays I/O-agnostic. The indexer does **not** hit the network — for NWT
chapters the caller passes a pre-fetched `NWTChapter` (constructed by the
CLI/MCP layer from `WOLClient`).
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
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
