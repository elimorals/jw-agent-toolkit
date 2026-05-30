"""Ingest pipeline: pull content from jw-core clients → chunk → embed → store.

High-level helpers for the common ingest targets:
  - Bible chapter (book_num, chapter)
  - Article (URL)
  - Daily text (one shot)
  - Search-result harvest (run a search and ingest the top N articles)
  - EPUB file (full publication, offline)
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from jw_core.clients.cdn import CDNClient
from jw_core.clients.wol import WOLClient
from jw_core.parsers.article import parse_article
from jw_core.parsers.epub import parse_epub
from jw_core.parsers.jw_library_backup import (
    BackupContents,
    parse_jw_library_backup,
)
from jw_core.parsers.jwpub import parse_jwpub

from jw_rag.chunker import chunk_paragraphs
from jw_rag.store import VectorStore

logger = logging.getLogger(__name__)


async def ingest_bible_chapter(
    store: VectorStore,
    book_num: int,
    chapter: int,
    *,
    language: str = "en",
    publication: str = "nwtsty",
    wol: WOLClient | None = None,
) -> int:
    """Ingest a single Bible chapter. Returns the number of chunks added."""
    owned = False
    if wol is None:
        wol = WOLClient()
        owned = True
    try:
        url, html = await wol.get_bible_chapter(book_num, chapter, language=language, publication=publication)
    finally:
        if owned:
            await wol.aclose()

    article = parse_article(html)
    chunks = chunk_paragraphs(
        article.paragraphs,
        source_id=f"bible:{book_num}:{chapter}:{language}",
        metadata={
            "kind": "bible_chapter",
            "book_num": book_num,
            "chapter": chapter,
            "language": language,
            "publication": publication,
            "title": article.title,
            "source_url": url,
        },
    )
    store.add(chunks)
    logger.info(f"Ingested Bible {book_num}:{chapter} ({language}) — {len(chunks)} chunks")
    return len(chunks)


async def ingest_article(
    store: VectorStore,
    url: str,
    *,
    wol: WOLClient | None = None,
    metadata: dict[str, Any] | None = None,
) -> int:
    """Ingest an arbitrary wol.jw.org article URL."""
    owned = False
    if wol is None:
        wol = WOLClient()
        owned = True
    try:
        html = await wol.fetch(url)
    finally:
        if owned:
            await wol.aclose()

    article = parse_article(html)
    chunks = chunk_paragraphs(
        article.paragraphs,
        source_id=f"article:{url}",
        metadata={
            "kind": "article",
            "title": article.title,
            "source_url": url,
            **(metadata or {}),
        },
    )
    store.add(chunks)
    logger.info(f"Ingested article {url!r} — {len(chunks)} chunks")
    return len(chunks)


async def ingest_search_topk(
    store: VectorStore,
    query: str,
    *,
    filter_type: str = "all",
    language: str = "E",
    top_n: int = 5,
    cdn: CDNClient | None = None,
    wol: WOLClient | None = None,
) -> int:
    """Run a jw.org search and ingest the top N article results.

    Returns the total number of chunks added across all ingested articles.
    """
    owned_cdn = False
    owned_wol = False
    if cdn is None:
        cdn = CDNClient()
        owned_cdn = True
    if wol is None:
        wol = WOLClient()
        owned_wol = True

    try:
        data = await cdn.search(query, filter_type=filter_type, language=language, limit=top_n)
        urls = _extract_article_urls(data, limit=top_n)
        total = 0
        for url in urls:
            try:
                total += await ingest_article(store, url, wol=wol)
            except Exception as e:
                logger.warning(f"Failed to ingest {url}: {e}")
        return total
    finally:
        if owned_cdn:
            await cdn.aclose()
        if owned_wol:
            await wol.aclose()


def _extract_article_urls(data: dict[str, Any], *, limit: int) -> list[str]:
    """Pull wol URLs out of the search response (flat or grouped shape)."""
    urls: list[str] = []
    for r in data.get("results", []):
        if isinstance(r, dict) and r.get("type") == "group":
            for inner in r.get("results", []):
                u = _wol_url_from(inner)
                if u:
                    urls.append(u)
        else:
            u = _wol_url_from(r)
            if u:
                urls.append(u)
        if len(urls) >= limit:
            break
    return urls[:limit]


def _wol_url_from(entry: dict[str, Any] | Any) -> str | None:
    if not isinstance(entry, dict):
        return None
    links = entry.get("links", {}) or {}
    return links.get("wol") or links.get("jw.org") or None


# ── Phase 5: EPUB ingest (the JWPUB-blocker workaround) ────────────────


def ingest_epub(
    store: VectorStore,
    epub_path: Path | str,
    *,
    publication_code: str = "",
    language: str = "en",
    skip_short_docs: int = 1,
) -> int:
    """Parse an EPUB file and ingest each document into the RAG store.

    Args:
        store: Open VectorStore to add chunks to.
        epub_path: Path to a downloaded `.epub` file.
        publication_code: Optional code (e.g. 'bh') stored on every chunk
            for later filtering.
        language: ISO code for the EPUB's language (cosmetic; we trust the
            EPUB metadata).
        skip_short_docs: Drop spine documents with fewer than N paragraphs
            (cover pages, dividers). Default 1 keeps everything with text.

    Returns:
        Total chunks added across all documents.
    """
    epub = parse_epub(epub_path)
    detected_lang = epub.language or language
    total = 0
    for doc in epub.documents:
        if len(doc.paragraphs) < skip_short_docs:
            continue
        chunks = chunk_paragraphs(
            doc.paragraphs,
            source_id=f"epub:{publication_code or epub.title}:{doc.id}",
            metadata={
                "kind": "epub_document",
                "publication": epub.title,
                "publication_code": publication_code,
                "language": detected_lang,
                "title": doc.title,
                "spine_index": doc.spine_index,
                "epub_href": doc.href,
                "source_path": str(epub_path),
            },
        )
        store.add(chunks)
        total += len(chunks)
    logger.info(f"Ingested EPUB {epub.title!r} ({epub.document_count} docs) → {total} chunks")
    return total


def ingest_jwpub(
    store: VectorStore,
    jwpub_path: Path | str,
    *,
    language: str = "en",
    skip_short_docs: int = 1,
) -> int:
    """Parse + decrypt a JWPUB file and ingest each document into RAG.

    Requires the publication's identity (language/symbol/year) to be
    present in the manifest — true for every JW-issued JWPUB. Raises
    `JwpubError` if the file isn't a valid JWPUB; individual blobs that
    fail to decrypt are skipped with a warning.

    Args:
        store: open VectorStore.
        jwpub_path: path to a .jwpub file.
        language: ISO code stored as metadata on every chunk.
        skip_short_docs: drop documents with fewer than N paragraphs
            (cover pages, TOCs).
    """
    pub = parse_jwpub(jwpub_path)
    if not pub.decrypted_text_available:
        logger.warning(
            f"No documents decrypted from {jwpub_path!r}. "
            f"The publication's identity may not match its content "
            f"(unusual format variant)."
        )
        return 0
    total = 0
    for doc in pub.documents:
        if len(doc.paragraphs) < skip_short_docs:
            continue
        chunks = chunk_paragraphs(
            doc.paragraphs,
            source_id=f"jwpub:{pub.symbol}:{doc.document_id}",
            metadata={
                "kind": "jwpub_document",
                "publication": pub.title,
                "publication_code": pub.symbol,
                "publication_type": pub.publication_type,
                "year": pub.year,
                "language": language,
                "title": doc.title or doc.toc_title,
                "chapter_number": doc.chapter_number,
                "section_number": doc.section_number,
                "first_page": doc.first_page_number,
                "last_page": doc.last_page_number,
                "source_path": str(jwpub_path),
            },
        )
        store.add(chunks)
        total += len(chunks)
    logger.info(f"Ingested JWPUB {pub.title!r} ({pub.document_count} docs) → {total} chunks")
    return total


# ── JW Library backup (Phase 19 — integrations) ────────────────────────


def ingest_jw_library_backup(
    store: VectorStore,
    backup_path: Path | str,
    *,
    include_titles: bool = True,
    include_bookmarks: bool = True,
    include_input_fields: bool = True,
    min_chars: int = 8,
) -> int:
    """Ingest the *user-authored* text of a `.jwlibrary` backup into RAG.

    Each note (and optionally bookmark snippet / input-field answer) becomes
    one chunk tagged with `kind="user_note"|"user_bookmark"|"user_input"`
    and the addressing fields (book/chapter/key_symbol/document_id). This
    lets the agent surface "what the user already studied" alongside the
    public corpus when answering questions.

    Args:
        store: open VectorStore.
        backup_path: path to a `.jwlibrary` archive.
        include_titles: prepend the note title to its content (cheap signal).
        include_bookmarks: also ingest bookmark snippets.
        include_input_fields: also ingest meeting-workbook answers etc.
        min_chars: drop entries shorter than this (empty notes, single-char).

    Returns:
        Total chunks added.
    """
    backup = parse_jw_library_backup(backup_path)
    total = 0
    total += _ingest_backup_notes(
        store,
        backup,
        include_titles=include_titles,
        min_chars=min_chars,
    )
    if include_bookmarks:
        total += _ingest_backup_bookmarks(store, backup, min_chars=min_chars)
    if include_input_fields:
        total += _ingest_backup_input_fields(store, backup, min_chars=min_chars)
    logger.info(
        "Ingested JW Library backup %r → %d chunks",
        backup.manifest.name or str(backup_path),
        total,
    )
    return total


def _ingest_backup_notes(
    store: VectorStore,
    backup: BackupContents,
    *,
    include_titles: bool,
    min_chars: int,
) -> int:
    total = 0
    for note in backup.notes:
        body_parts: list[str] = []
        if include_titles and note.title:
            body_parts.append(note.title)
        if note.content:
            body_parts.append(note.content)
        body = "\n".join(body_parts).strip()
        if len(body) < min_chars:
            continue
        chunks = chunk_paragraphs(
            [body],
            source_id=f"jwlib:note:{note.note_id}",
            metadata=_note_metadata(backup, note),
        )
        store.add(chunks)
        total += len(chunks)
    return total


def _note_metadata(backup: BackupContents, note: object) -> dict[str, Any]:
    md: dict[str, Any] = {
        "kind": "user_note",
        "note_id": getattr(note, "note_id", None),
        "guid": getattr(note, "guid", ""),
        "created": getattr(note, "created", ""),
        "last_modified": getattr(note, "last_modified", ""),
        "tags": list(getattr(note, "tags", []) or []),
        "source_backup": backup.manifest.name or backup.source_path,
    }
    loc = getattr(note, "location", None)
    if loc is not None:
        md.update(
            {
                "book_num": loc.book_number,
                "chapter": loc.chapter_number,
                "key_symbol": loc.key_symbol,
                "document_id": loc.document_id,
                "meps_language": loc.meps_language,
            }
        )
    return md


def _ingest_backup_bookmarks(
    store: VectorStore,
    backup: BackupContents,
    *,
    min_chars: int,
) -> int:
    total = 0
    for bm in backup.bookmarks:
        body = "\n".join(p for p in (bm.title, bm.snippet) if p).strip()
        if len(body) < min_chars:
            continue
        chunks = chunk_paragraphs(
            [body],
            source_id=f"jwlib:bookmark:{bm.bookmark_id}",
            metadata={
                "kind": "user_bookmark",
                "bookmark_id": bm.bookmark_id,
                "slot": bm.slot,
                "book_num": bm.location.book_number,
                "chapter": bm.location.chapter_number,
                "key_symbol": bm.location.key_symbol,
                "document_id": bm.location.document_id,
                "source_backup": backup.manifest.name or backup.source_path,
            },
        )
        store.add(chunks)
        total += len(chunks)
    return total


def _ingest_backup_input_fields(
    store: VectorStore,
    backup: BackupContents,
    *,
    min_chars: int,
) -> int:
    total = 0
    for f in backup.input_fields:
        if len(f.value or "") < min_chars:
            continue
        chunks = chunk_paragraphs(
            [f.value],
            source_id=f"jwlib:input:{f.location_id}:{f.text_tag}",
            metadata={
                "kind": "user_input",
                "location_id": f.location_id,
                "text_tag": f.text_tag,
                "key_symbol": getattr(f.location, "key_symbol", "") if f.location else "",
                "document_id": getattr(f.location, "document_id", None) if f.location else None,
                "source_backup": backup.manifest.name or backup.source_path,
            },
        )
        store.add(chunks)
        total += len(chunks)
    return total
