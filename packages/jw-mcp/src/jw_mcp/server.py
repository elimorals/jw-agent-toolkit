"""jw-agent-toolkit MCP server.

Exposes 5 tools (Phase 1 MVP) over the Model Context Protocol:

  - resolve_reference  → parse "Juan 3:16" → BibleRef + canonical wol URL
  - get_chapter        → fetch and parse a Bible chapter from wol.jw.org
  - get_daily_text     → today's text in the requested language
  - search_content     → jw.org search via the CDN JSON API
  - get_article        → fetch and parse an arbitrary wol.jw.org article

Run with:  uv run jw-mcp
Communicates via stdio (default MCP transport).
"""

from __future__ import annotations

import logging
from typing import Any

from fastmcp import FastMCP
from jw_agents import (
    apologetics as apologetics_agent,
)
from jw_agents import (
    meeting_helper as meeting_helper_agent,
)
from jw_agents import (
    research_topic as research_topic_agent,
)
from jw_agents import (
    verse_explainer as verse_explainer_agent,
)
from jw_core.clients.cdn import CDNClient
from jw_core.clients.mediator import MediatorClient
from jw_core.clients.pub_media import PubMediaClient, PubMediaError
from jw_core.clients.topic_index import TopicIndexClient, TopicIndexError
from jw_core.clients.wol import WOLClient
from jw_core.languages import get_language
from jw_core.parsers.article import parse_article
from jw_core.parsers.daily_text import parse_daily_text
from jw_core.parsers.epub import parse_epub
from jw_core.parsers.jwpub import JwpubError, parse_jwpub, parse_jwpub_metadata
from jw_core.parsers.reference import parse_reference
from jw_core.parsers.study_notes import (
    parse_cross_references,
    parse_study_notes,
    study_notes_for_verse,
)
from jw_core.parsers.verse import get_verse as _get_verse_from_html
from jw_rag import FakeEmbedder, VectorStore

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("jw-mcp")

mcp = FastMCP("jw-agent-toolkit")

# Shared clients (created lazily on first use, closed on shutdown).
_wol: WOLClient | None = None
_cdn: CDNClient | None = None
_pub: PubMediaClient | None = None
_med: MediatorClient | None = None
_topic: TopicIndexClient | None = None


def _get_wol() -> WOLClient:
    global _wol
    if _wol is None:
        _wol = WOLClient()
    return _wol


def _get_cdn() -> CDNClient:
    global _cdn
    if _cdn is None:
        _cdn = CDNClient()
    return _cdn


def _get_pub() -> PubMediaClient:
    global _pub
    if _pub is None:
        _pub = PubMediaClient()
    return _pub


def _get_med() -> MediatorClient:
    global _med
    if _med is None:
        _med = MediatorClient()
    return _med


def _get_topic() -> TopicIndexClient:
    global _topic
    if _topic is None:
        # Reuse the shared CDN + WOL clients so we don't double the
        # connection pool.
        _topic = TopicIndexClient(cdn=_get_cdn(), wol=_get_wol())
    return _topic


# RAG store (lazy, configurable via env var).
_rag_store: VectorStore | None = None
_rag_path = None


def _get_rag_store() -> VectorStore:
    """Open the configured RAG store (creating an empty one if necessary).

    Path comes from JW_RAG_STORE_PATH env var, defaulting to
    ~/.jw-agent-toolkit/rag/. Embedder dim defaults to 64 via FakeEmbedder.
    Override the embedder by editing this function — Phase 6 keeps the
    default fake so the MCP works offline out of the box.
    """
    import os
    from pathlib import Path

    global _rag_store, _rag_path
    if _rag_store is not None:
        return _rag_store
    path = Path(os.getenv("JW_RAG_STORE_PATH", "~/.jw-agent-toolkit/rag")).expanduser()
    path.mkdir(parents=True, exist_ok=True)
    _rag_store = VectorStore(path, FakeEmbedder(dim=64))
    try:
        _rag_store.load()
    except Exception as e:
        logger.warning(f"RAG store load failed (starting empty): {e}")
    _rag_path = path
    return _rag_store


# ────────────────────────────────────────────────────────────────────────
# Tool: resolve_reference
# ────────────────────────────────────────────────────────────────────────


@mcp.tool
def resolve_reference(text: str, language: str = "en") -> dict[str, Any]:
    """Parse a Bible reference and return its canonical structure plus URL.

    Recognizes English, Spanish, and Portuguese names + JW NWT abbreviations.
    Examples that work: "Juan 3:16", "1 Co 13:4-7", "Heb 13", "John 3:16-18".

    Args:
        text: Free-form text containing a Bible reference.
        language: ISO code ('en', 'es', 'pt') for the wol.jw.org URL.

    Returns:
        Structured reference with book_num, chapter, verses, detected language,
        and a canonical wol.jw.org URL. Returns an `error` field if no
        reference could be parsed.
    """
    ref = parse_reference(text)
    if ref is None:
        return {"error": f"No Bible reference detected in: {text!r}"}
    return {
        "book_num": ref.book_num,
        "book_canonical": ref.book_canonical,
        "chapter": ref.chapter,
        "verse_start": ref.verse_start,
        "verse_end": ref.verse_end,
        "detected_language": ref.detected_language,
        "display": ref.display(),
        "raw_match": ref.raw_match,
        "wol_url": ref.wol_url(lang=language),
    }


# ────────────────────────────────────────────────────────────────────────
# Tool: get_chapter
# ────────────────────────────────────────────────────────────────────────


@mcp.tool
async def get_chapter(
    book_num: int,
    chapter: int,
    language: str = "en",
    publication: str = "nwtsty",
    with_footnotes: bool = False,
) -> dict[str, Any]:
    """Fetch a Bible chapter from wol.jw.org and return its parsed text.

    Args:
        book_num: 1-66 (Genesis=1, Revelation=66).
        chapter: Chapter number.
        language: ISO language code (en/es/pt).
        publication: Bible edition. Default 'nwtsty' (NWT Study Edition).
        with_footnotes: When True, additionally fetch the study notes for
            this chapter (mapped to verse via the Phase 3.5 heuristic) and
            cross-reference markers.

    Returns:
        title, paragraphs[], references[], source_url. When
        `with_footnotes=True`, also `study_notes[]` and `cross_refs[]`.
    """
    if not 1 <= book_num <= 66:
        return {"error": f"book_num must be 1..66, got {book_num}"}
    wol = _get_wol()
    url, html = await wol.get_bible_chapter(book_num, chapter, language=language, publication=publication)
    article = parse_article(html)
    payload: dict[str, Any] = {
        "title": article.title,
        "paragraphs": article.paragraphs,
        "references": article.references,
        "source_url": url,
        "language": language,
        "publication": publication,
    }
    if with_footnotes:
        notes = parse_study_notes(html, book_num=book_num, chapter=chapter, language=language)
        xrefs = parse_cross_references(html, book_num=book_num, chapter=chapter, language=language)
        payload["study_notes"] = [n.model_dump() for n in notes]
        payload["cross_refs"] = [x.model_dump() for x in xrefs]
    return payload


# ────────────────────────────────────────────────────────────────────────
# Tool: get_daily_text
# ────────────────────────────────────────────────────────────────────────


@mcp.tool
async def get_daily_text(language: str = "en", date: str = "") -> dict[str, Any]:
    """Fetch the daily text from wol.jw.org.

    Args:
        language: ISO language code (en/es/pt).
        date: Optional ISO `YYYY-MM-DD`. When empty, returns today's
            text from the WOL homepage. When set, navigates to the
            date-specific path (works for any date the WOL site has
            published, typically several years back).

    Returns:
        date, scripture, commentary, source_url. If parsing fails, returns
        the raw HTML length so the caller can debug.
    """
    wol = _get_wol()
    if date:
        try:
            url, html = await wol.get_daily_text_by_date(date, language=language)
        except Exception as e:
            return {"error": f"Could not fetch daily text for {date}: {e}"}
    else:
        url, html = await wol.get_today_homepage(language=language)
    text = parse_daily_text(html)
    if text is None:
        return {
            "error": "Could not extract daily text from page HTML",
            "source_url": url,
            "html_length": len(html),
        }
    return {
        "date": text.date,
        "scripture": text.scripture,
        "commentary": text.commentary,
        "source_url": url,
        "language": language,
        "requested_date": date or "today",
    }


# ────────────────────────────────────────────────────────────────────────
# Tool: search_content
# ────────────────────────────────────────────────────────────────────────


@mcp.tool
async def search_content(
    query: str,
    filter_type: str = "all",
    language: str = "en",
    limit: int = 10,
) -> dict[str, Any]:
    """Search jw.org content via the CDN JSON API.

    Args:
        query: Search terms.
        filter_type: One of 'all', 'publications', 'videos', 'audio', 'bible',
            'indexes'. Default 'all'.
        language: ISO code; converted to JW code internally (en→E, es→S).
        limit: Truncate to N results (the API does not support a server-side
            limit, so we slice client-side).
    """
    try:
        lang = get_language(language)
    except KeyError:
        return {"error": f"Unknown language: {language!r}"}
    cdn = _get_cdn()
    try:
        data = await cdn.search(query, filter_type=filter_type, language=lang.jw_code, limit=limit)
    except Exception as e:
        return {"error": str(e)}
    return {
        "query": query,
        "filter_type": filter_type,
        "language": language,
        "results": data,
    }


# ────────────────────────────────────────────────────────────────────────
# Tool: get_article
# ────────────────────────────────────────────────────────────────────────


@mcp.tool
async def get_article(url: str) -> dict[str, Any]:
    """Fetch any wol.jw.org URL and parse it as an article.

    Args:
        url: A wol.jw.org article URL (or a path starting with /).

    Returns:
        title, paragraphs[], references[], source_url.
    """
    wol = _get_wol()
    html = await wol.fetch(url)
    article = parse_article(html)
    return {
        "title": article.title,
        "paragraphs": article.paragraphs,
        "references": article.references,
        "source_url": url,
    }


# ────────────────────────────────────────────────────────────────────────
# Tool: list_languages (Phase 2)
# ────────────────────────────────────────────────────────────────────────


@mcp.tool
async def list_languages(
    in_language: str = "E",
    only_with_web_content: bool = True,
) -> dict[str, Any]:
    """List languages available on jw.org with JW + ISO codes.

    Args:
        in_language: JW code of the language to display names in (e.g. 'E', 'S').
        only_with_web_content: Drop languages without web content.

    Returns:
        A list of language entries with `code`, `locale` (ISO), `name`,
        `vernacular`, `rtl`, `is_sign_language`.
    """
    med = _get_med()
    try:
        langs = await med.list_languages(in_language=in_language)
    except Exception as e:
        return {"error": str(e)}
    items = [l.model_dump() for l in langs if not only_with_web_content or l.has_web_content]
    return {"in_language": in_language, "count": len(items), "languages": items}


# ────────────────────────────────────────────────────────────────────────
# Tool: list_publication_files (Phase 2)
# ────────────────────────────────────────────────────────────────────────


@mcp.tool
async def list_publication_files(
    pub_code: str,
    language: str = "E",
    file_format: str | None = None,
    bible_book: int | None = None,
    issue: int | None = None,
) -> dict[str, Any]:
    """List downloadable files for a publication (no download — just metadata).

    Args:
        pub_code: JW publication code (e.g. 'fg', 'nwt', 'rr').
        language: JW language code (e.g. 'E', 'S').
        file_format: Optional filter — PDF, EPUB, JWPUB, MP3, RTF, BRL.
        bible_book: Optional book number 1..66 (for Bible publications).
        issue: Optional YYYYMM (for magazines).

    Returns:
        Publication metadata + a list of files with URLs and sizes.
    """
    pub = _get_pub()
    try:
        publication = await pub.get_publication(
            pub_code,
            language=language,
            issue=issue,
            bible_book=bible_book,
            file_format=file_format,
        )
    except PubMediaError as e:
        return {"error": str(e)}
    return {
        "pub_code": publication.pub_code,
        "pub_name": publication.pub_name,
        "file_count": len(publication.files),
        "files": [f.model_dump() for f in publication.files],
    }


# ────────────────────────────────────────────────────────────────────────
# Tool: download_publication (Phase 2)
# ────────────────────────────────────────────────────────────────────────


@mcp.tool
async def download_publication(
    pub_code: str,
    out_dir: str,
    language: str = "E",
    file_format: str = "EPUB",
    bible_book: int | None = None,
    issue: int | None = None,
) -> dict[str, Any]:
    """Download a publication to a local directory.

    Args:
        pub_code: JW publication code.
        out_dir: Absolute path to the output directory.
        language: JW language code.
        file_format: PDF/EPUB/JWPUB/MP3/RTF/BRL.
        bible_book: Optional 1..66.
        issue: Optional YYYYMM.

    Returns:
        A list of saved file paths and total bytes downloaded.
    """
    from pathlib import Path

    out_path = Path(out_dir).expanduser()
    out_path.mkdir(parents=True, exist_ok=True)
    pub = _get_pub()
    try:
        publication = await pub.get_publication(
            pub_code,
            language=language,
            issue=issue,
            bible_book=bible_book,
            file_format=file_format,
        )
        files = publication.files_by_format(file_format)
        if not files:
            return {
                "error": f"No {file_format} files for {pub_code!r} in {language!r}",
            }
        saved: list[dict[str, Any]] = []
        total_bytes = 0
        for f in files:
            dest = await pub.download(f, out_path / f.filename)
            saved.append({"path": str(dest), "size_bytes": f.size_bytes})
            total_bytes += f.size_bytes
        return {
            "pub_code": pub_code,
            "language": language,
            "file_format": file_format,
            "saved": saved,
            "total_bytes": total_bytes,
        }
    except PubMediaError as e:
        return {"error": str(e)}


# ────────────────────────────────────────────────────────────────────────
# Tool: get_verse (Phase 3)
# ────────────────────────────────────────────────────────────────────────


@mcp.tool
async def get_verse(
    book_num: int,
    chapter: int,
    verse: int,
    language: str = "en",
) -> dict[str, Any]:
    """Fetch the clean text of a single Bible verse from wol.jw.org (nwtsty).

    The returned text is stripped of pronunciation marks (·, ʹ), inline
    cross-ref markers (+), and footnote markers (*).

    Args:
        book_num: 1..66 (Genesis=1, Revelation=66).
        chapter: Chapter number.
        verse: Verse number.
        language: ISO code (en/es/pt).
    """
    if not 1 <= book_num <= 66:
        return {"error": f"book_num must be 1..66, got {book_num}"}
    wol = _get_wol()
    url, html = await wol.get_bible_chapter(book_num, chapter, language=language)
    v = _get_verse_from_html(html, book_num, chapter, verse, language=language)
    if v is None:
        return {"error": f"Verse {book_num}:{chapter}:{verse} not found", "source_url": url}
    return {
        "book_num": v.book_num,
        "chapter": v.chapter,
        "verse": v.verse,
        "text": v.text,
        "language": v.language,
        "wol_url": v.wol_url(),
        "source_url": url,
    }


# ────────────────────────────────────────────────────────────────────────
# Tool: get_study_notes (Phase 3)
# ────────────────────────────────────────────────────────────────────────


@mcp.tool
async def get_study_notes(
    book_num: int,
    chapter: int,
    verse: int | None = None,
    language: str = "en",
) -> dict[str, Any]:
    """Fetch NWT Study Edition (nwtsty) commentary for a chapter or specific verse.

    Returns the headword each note annotates, the commentary body, and any
    inline cross-references the note cites. Only English currently has full
    nwtsty notes; other languages may return fewer or none.

    Args:
        book_num: 1..66.
        chapter: Chapter number.
        verse: Optional — filter to notes mapped to this verse only.
        language: ISO code.
    """
    if not 1 <= book_num <= 66:
        return {"error": f"book_num must be 1..66, got {book_num}"}
    wol = _get_wol()
    url, html = await wol.get_bible_chapter(book_num, chapter, language=language)
    notes = parse_study_notes(html, book_num=book_num, chapter=chapter, language=language)
    if verse is not None:
        notes = study_notes_for_verse(notes, verse)
    return {
        "book_num": book_num,
        "chapter": chapter,
        "verse": verse,
        "language": language,
        "source_url": url,
        "count": len(notes),
        "notes": [n.model_dump() for n in notes],
    }


# ────────────────────────────────────────────────────────────────────────
# Tool: get_cross_references (Phase 3)
# ────────────────────────────────────────────────────────────────────────


@mcp.tool
async def get_cross_references(
    book_num: int,
    chapter: int,
    verse: int | None = None,
    language: str = "en",
    resolve_panel: bool = False,
) -> dict[str, Any]:
    """Get inline cross-reference markers from a Bible chapter.

    Each marker points at a WOL cross-references panel via its `href`. Set
    `resolve_panel=True` to ALSO fetch each panel — slower (one extra
    request per cross-ref) but you get the actual parallel scriptures.

    Args:
        book_num: 1..66.
        chapter: Chapter number.
        verse: Optional — filter to markers in this verse only.
        language: ISO code.
        resolve_panel: Whether to fetch the cross-ref panel HTML for each.
    """
    if not 1 <= book_num <= 66:
        return {"error": f"book_num must be 1..66, got {book_num}"}
    wol = _get_wol()
    url, html = await wol.get_bible_chapter(book_num, chapter, language=language)
    refs = parse_cross_references(html, book_num=book_num, chapter=chapter, language=language)
    if verse is not None:
        refs = [r for r in refs if r.verse == verse]

    payload: list[dict[str, Any]] = []
    for r in refs:
        item = r.model_dump()
        item["full_url"] = r.full_url()
        if resolve_panel:
            try:
                panel_url, panel_html = await wol.get_cross_reference_panel(r.href)
                item["panel_url"] = panel_url
                # Lightweight: extract just the visible text content.
                from bs4 import BeautifulSoup

                item["panel_text"] = BeautifulSoup(panel_html, "lxml").get_text(" ", strip=True)[:600]
            except Exception as e:
                item["panel_error"] = str(e)
        payload.append(item)

    return {
        "book_num": book_num,
        "chapter": chapter,
        "verse": verse,
        "language": language,
        "source_url": url,
        "count": len(payload),
        "cross_references": payload,
    }


# ────────────────────────────────────────────────────────────────────────
# Tool: compare_translations (Phase 3)
# ────────────────────────────────────────────────────────────────────────


@mcp.tool
async def compare_translations(
    book_num: int,
    chapter: int,
    verse: int,
    languages: list[str] | None = None,
) -> dict[str, Any]:
    """Fetch the same verse in multiple languages side by side.

    Args:
        book_num: 1..66.
        chapter: Chapter number.
        verse: Verse number.
        languages: ISO codes — defaults to ['en', 'es', 'pt']. Each language
            uses its preferred Bible edition (nwtsty for English; nwt for the
            others). The fetch runs sequentially to keep load light.
    """
    if not 1 <= book_num <= 66:
        return {"error": f"book_num must be 1..66, got {book_num}"}
    langs = languages or ["en", "es", "pt"]
    wol = _get_wol()
    out: dict[str, Any] = {}
    for lang in langs:
        try:
            url, html = await wol.get_bible_chapter(book_num, chapter, language=lang)
            v = _get_verse_from_html(html, book_num, chapter, verse, language=lang)
            out[lang] = {
                "text": v.text if v else None,
                "wol_url": v.wol_url() if v else url,
                "found": v is not None,
            }
        except Exception as e:
            out[lang] = {"error": str(e)}
    return {
        "book_num": book_num,
        "chapter": chapter,
        "verse": verse,
        "translations": out,
    }


# ────────────────────────────────────────────────────────────────────────
# Tool: search_topic_index (Phase 4)
# ────────────────────────────────────────────────────────────────────────


@mcp.tool
async def search_topic_index(query: str, language: str = "E", limit: int = 10) -> dict[str, Any]:
    """Find Watch Tower Publications Index subjects matching `query`.

    The Publications Index is the official JW topical index that groups
    publications, articles, and Bible refs by subject (e.g. "Trinity",
    "Soul", "Last Days"). This is the authoritative entry point for
    doctrinal research.

    Returns candidate subjects with title, snippet, docid, and wol_url.
    Feed a docid into `get_topic_articles` to retrieve the full subject.

    Args:
        query: Topic or subject phrase.
        language: JW code ('E', 'S', 'T').
        limit: Max candidate subjects.
    """
    try:
        results = await _get_topic().search_subjects(query, language=language, limit=limit)
    except TopicIndexError as e:
        return {"error": str(e)}
    return {"query": query, "language": language, "count": len(results), "results": results}


# ────────────────────────────────────────────────────────────────────────
# Tool: get_topic_articles (Phase 4)
# ────────────────────────────────────────────────────────────────────────


@mcp.tool
async def get_topic_articles(docid_or_url: str, language: str = "en") -> dict[str, Any]:
    """Fetch and parse a Publications Index subject page.

    Args:
        docid_or_url: WOL document id (e.g. '1200275936' for Trinity) OR a
            full wol.jw.org URL.
        language: ISO code for URL building when given a bare docid.

    Returns the subject title, see-also references, and an ordered list of
    subheadings — each with its heading, top_level flag, and citations
    (Bible refs with URLs + publication abbreviations as plain text).
    """
    try:
        subject = await _get_topic().get_subject_page(docid_or_url, language=language)
    except TopicIndexError as e:
        return {"error": str(e)}
    return {
        "docid": subject.docid,
        "title": subject.title,
        "see_also": subject.see_also,
        "source_url": subject.source_url,
        "language": subject.language,
        "total_citations": subject.total_citations,
        "subheadings": [
            {
                "heading": sh.heading,
                "is_top_level": sh.is_top_level,
                "citations": [c.model_dump() for c in sh.citations],
            }
            for sh in subject.subheadings
        ],
    }


# ────────────────────────────────────────────────────────────────────────
# Tool: semantic_search (Phase 6)
# ────────────────────────────────────────────────────────────────────────


@mcp.tool
def semantic_search(query: str, top_k: int = 5, mode: str = "hybrid") -> dict[str, Any]:
    """Search the local RAG store (Bible chapters + ingested articles).

    The store is created on demand at JW_RAG_STORE_PATH (default
    ~/.jw-agent-toolkit/rag/). Empty until you ingest content via
    `ingest_bible_chapter` / `ingest_article` / `ingest_search_topk`.

    Args:
        query: Free-text query.
        top_k: Number of results.
        mode: 'hybrid' (default), 'vector', or 'bm25'.
    """
    store = _get_rag_store()
    if store.is_empty:
        return {
            "warning": "RAG store is empty. Call ingest_bible_chapter or ingest_search_topk first.",
            "results": [],
        }
    if mode == "vector":
        hits = store.vector_search(query, top_k=top_k)
    elif mode == "bm25":
        hits = store.bm25_search(query, top_k=top_k)
    else:
        hits = store.hybrid_search(query, top_k=top_k)
    return {
        "query": query,
        "mode": mode,
        "count": len(hits),
        "results": [
            {
                "rank": h.rank,
                "score": h.score,
                "source": h.source,
                "chunk_id": h.chunk.id,
                "text": h.chunk.text,
                "metadata": h.chunk.metadata,
            }
            for h in hits
        ],
    }


# ────────────────────────────────────────────────────────────────────────
# Tool: ingest_bible_chapter (Phase 6)
# ────────────────────────────────────────────────────────────────────────


@mcp.tool
async def ingest_bible_chapter(book_num: int, chapter: int, language: str = "en") -> dict[str, Any]:
    """Fetch a Bible chapter from wol.jw.org and add it to the local RAG store."""
    if not 1 <= book_num <= 66:
        return {"error": f"book_num must be 1..66, got {book_num}"}
    from jw_rag.ingest import ingest_bible_chapter as _ingest

    store = _get_rag_store()
    count = await _ingest(store, book_num, chapter, language=language, wol=_get_wol())
    store.save()
    return {
        "book_num": book_num,
        "chapter": chapter,
        "language": language,
        "chunks_added": count,
        "store_total": store.count,
    }


# ────────────────────────────────────────────────────────────────────────
# Tool: ingest_search_topk (Phase 6)
# ────────────────────────────────────────────────────────────────────────


@mcp.tool
async def ingest_search_topk(
    query: str,
    top_n: int = 5,
    filter_type: str = "all",
    language: str = "E",
) -> dict[str, Any]:
    """Run a jw.org search and ingest the top N article results into RAG."""
    from jw_rag.ingest import ingest_search_topk as _ingest

    store = _get_rag_store()
    total = await _ingest(
        store,
        query,
        filter_type=filter_type,
        language=language,
        top_n=top_n,
        cdn=_get_cdn(),
        wol=_get_wol(),
    )
    store.save()
    return {
        "query": query,
        "ingested_articles": top_n,
        "chunks_added": total,
        "store_total": store.count,
    }


# ────────────────────────────────────────────────────────────────────────
# Tool: research_topic (Phase 7)
# ────────────────────────────────────────────────────────────────────────


@mcp.tool
async def research_topic(
    topic: str,
    language: str = "E",
    top_n: int = 5,
    fetch_top_k: int = 3,
) -> dict[str, Any]:
    """Multi-step topic research: search jw.org → fetch top articles → return excerpts with citations."""
    result = await research_topic_agent(
        topic,
        language=language,
        top_n=top_n,
        fetch_top_k=fetch_top_k,
        cdn=_get_cdn(),
        wol=_get_wol(),
    )
    return result.to_dict()


# ────────────────────────────────────────────────────────────────────────
# Tool: verse_explainer (Phase 7)
# ────────────────────────────────────────────────────────────────────────


@mcp.tool
async def verse_explainer(reference: str, language: str = "en", max_paragraphs: int = 5) -> dict[str, Any]:
    """Explain a verse with surrounding context + cross-references from wol.jw.org."""
    result = await verse_explainer_agent(
        reference,
        language=language,
        wol=_get_wol(),
        max_paragraphs=max_paragraphs,
    )
    return result.to_dict()


# ────────────────────────────────────────────────────────────────────────
# Tool: meeting_helper (Phase 7)
# ────────────────────────────────────────────────────────────────────────


@mcp.tool
async def meeting_helper(input_text: str, language: str = "en", max_paragraphs: int = 8) -> dict[str, Any]:
    """Build meeting-prep findings from a wol.jw.org URL or a Bible reference."""
    result = await meeting_helper_agent(
        input_text,
        language=language,
        max_paragraphs=max_paragraphs,
        wol=_get_wol(),
    )
    return result.to_dict()


# ────────────────────────────────────────────────────────────────────────
# Tool: apologetics (Phase 7)
# ────────────────────────────────────────────────────────────────────────


@mcp.tool
async def apologetics(
    question: str,
    language: str = "E",
    web_top_k: int = 3,
    use_rag: bool = True,
    rag_top_k: int = 5,
) -> dict[str, Any]:
    """Answer a doctrinal question with citations only from jw.org sources.

    If `use_rag=True` (default) and the local RAG store has any chunks,
    they're hybrid-searched alongside the CDN search results.
    """
    rag_store = None
    if use_rag:
        s = _get_rag_store()
        rag_store = s if not s.is_empty else None
    result = await apologetics_agent(
        question,
        language=language,
        cdn=_get_cdn(),
        wol=_get_wol(),
        rag_store=rag_store,
        rag_top_k=rag_top_k,
        web_top_k=web_top_k,
    )
    return result.to_dict()


# ────────────────────────────────────────────────────────────────────────
# Tool: extract_epub_text (Phase 5)
# ────────────────────────────────────────────────────────────────────────


@mcp.tool
def extract_epub_text(epub_path: str, max_docs: int = 0) -> dict[str, Any]:
    """Parse a downloaded JW EPUB file and return its full text.

    EPUB is the open-standard alternative to JWPUB. JW publishes most
    recent material in both formats; this tool works on the EPUB side
    because JWPUB content is AES-encrypted with a non-public key
    derivation (see ROADMAP — Phase 5).

    Pair with `download_publication(pub_code, format='EPUB', out_dir=...)`
    from Phase 2 to get the file in the first place.

    Args:
        epub_path: Absolute path to a downloaded .epub file.
        max_docs: Limit returned documents to the first N (0 = all).

    Returns:
        Title, creator, language, identifier, and an ordered list of
        documents with id/title/href/paragraphs/spine_index.
    """
    try:
        epub = parse_epub(epub_path)
    except Exception as e:
        return {"error": f"Could not parse EPUB at {epub_path!r}: {e}"}
    docs = epub.documents[:max_docs] if max_docs > 0 else epub.documents
    return {
        "title": epub.title,
        "creator": epub.creator,
        "language": epub.language,
        "identifier": epub.identifier,
        "publisher": epub.publisher,
        "document_count": epub.document_count,
        "paragraph_count": epub.paragraph_count,
        "source_path": epub.source_path,
        "documents": [d.model_dump() for d in docs],
    }


# ────────────────────────────────────────────────────────────────────────
# Tool: inspect_jwpub_metadata (Phase 5)
# ────────────────────────────────────────────────────────────────────────


@mcp.tool
def inspect_jwpub_metadata(jwpub_path: str) -> dict[str, Any]:
    """Parse a JWPUB file's metadata + chapter TOC (no decryption — cheap).

    Returns title, symbol, publication_type, year, manifest_hash, schema
    version, and a TOC with title/chapter/section/paragraph counts/page
    ranges. To also decrypt the text, use `extract_jwpub_text` instead.

    Args:
        jwpub_path: Absolute path to a downloaded .jwpub file.
    """
    try:
        meta = parse_jwpub_metadata(jwpub_path)
    except JwpubError as e:
        return {"error": str(e)}
    return meta.model_dump(exclude={"documents": {"__all__": {"text"}}})


# ────────────────────────────────────────────────────────────────────────
# Tool: extract_jwpub_text (Phase 5.5)
# ────────────────────────────────────────────────────────────────────────


@mcp.tool
def extract_jwpub_text(jwpub_path: str, max_docs: int = 0) -> dict[str, Any]:
    """Decrypt and return the full text of a JWPUB publication.

    Uses the AES-128-CBC key derivation discovered by `gokusander/
    jwpub-toolkit` (`SHA256(f"{lang}_{symbol}_{year}") XOR magic_constant`).
    Works for every JW-issued JWPUB we've tested (publication identity
    must be present in the manifest, which is always the case).

    Each document carries `text` (decrypted XHTML) and `paragraphs`
    (plain-text body, ready for chunking/RAG).

    Args:
        jwpub_path: Absolute path to a downloaded .jwpub file.
        max_docs: Limit returned documents to the first N (0 = all).
    """
    try:
        pub = parse_jwpub(jwpub_path)
    except JwpubError as e:
        return {"error": str(e)}
    docs = pub.documents[:max_docs] if max_docs > 0 else pub.documents
    return {
        "title": pub.title,
        "symbol": pub.symbol,
        "year": pub.year,
        "publication_type": pub.publication_type,
        "language_index": pub.language_index,
        "document_count": pub.document_count,
        "decrypted_text_available": pub.decrypted_text_available,
        "source_path": pub.source_path,
        "documents": [d.model_dump() for d in docs],
    }


# ────────────────────────────────────────────────────────────────────────
# Tool: ingest_jwpub (Phase 5.5)
# ────────────────────────────────────────────────────────────────────────


@mcp.tool
def ingest_jwpub(jwpub_path: str, language: str = "en") -> dict[str, Any]:
    """Decrypt a JWPUB and ingest every document into the local RAG store.

    Args:
        jwpub_path: Absolute path to a downloaded .jwpub file.
        language: ISO code attached to every chunk for later filtering.
    """
    from jw_rag.ingest import ingest_jwpub as _ingest_jwpub

    store = _get_rag_store()
    try:
        total = _ingest_jwpub(store, jwpub_path, language=language)
    except Exception as e:
        return {"error": str(e)}
    store.save()
    return {
        "jwpub_path": jwpub_path,
        "language": language,
        "chunks_added": total,
        "store_total": store.count,
    }


# ────────────────────────────────────────────────────────────────────────
# Tool: ingest_epub (Phase 5)
# ────────────────────────────────────────────────────────────────────────


@mcp.tool
def ingest_epub(
    epub_path: str,
    publication_code: str = "",
    language: str = "en",
) -> dict[str, Any]:
    """Ingest a downloaded JW EPUB into the local RAG store.

    Args:
        epub_path: Absolute path to a downloaded .epub file.
        publication_code: Optional code (e.g. 'bh' for Bible Teach) stored
            on every chunk for later filtering.
        language: ISO code for the publication's language.
    """
    from jw_rag.ingest import ingest_epub as _ingest_epub

    store = _get_rag_store()
    try:
        total = _ingest_epub(
            store,
            epub_path,
            publication_code=publication_code,
            language=language,
        )
    except Exception as e:
        return {"error": str(e)}
    store.save()
    return {
        "epub_path": epub_path,
        "publication_code": publication_code,
        "language": language,
        "chunks_added": total,
        "store_total": store.count,
    }


# ────────────────────────────────────────────────────────────────────────
# Tool: get_cache_stats (Phase 9)
# ────────────────────────────────────────────────────────────────────────


@mcp.tool
def get_cache_stats() -> dict[str, Any]:
    """Return cache statistics for the on-disk response cache.

    When the server is started without a configured `DiskCache`, returns
    `enabled=False`. Otherwise reports total/live/expired entries plus the
    file path so the operator can inspect or clean it.
    """
    import os
    from pathlib import Path

    from jw_core.cache import DiskCache as _Cache

    # The server doesn't wire a persistent cache by default — return a
    # standalone snapshot of the disk store (matching the path the wired
    # clients would use). This avoids forcing every callsite to share state.
    path = Path(os.getenv("JW_CACHE_PATH", "~/.jw-agent-toolkit/cache.db")).expanduser()
    if not path.exists():
        return {"enabled": False, "path": str(path), "reason": "no cache file"}
    with _Cache(path) as c:
        stats = c.stats()
    return {"enabled": True, "path": str(path), **stats}


# ────────────────────────────────────────────────────────────────────────
# Tool: get_publication_toc (Phase 2 — gap from original plan)
# ────────────────────────────────────────────────────────────────────────


@mcp.tool
async def get_publication_toc(
    pub_code: str,
    language: str = "en",
    number: int | None = None,
) -> dict[str, Any]:
    """Fetch a publication's landing page (Table of Contents) on wol.jw.org.

    URL pattern: `/{iso}/wol/publication/{r}/{lp_tag}/{pub}[/{number}]`.
    For Bible editions like `nwtsty`, `number` selects a book TOC. For
    magazines, `number` is the issue index. For books, the chapter.

    Args:
        pub_code: JW publication code (e.g. 'nwtsty', 'rr', 'fg', 'w24.04').
        language: ISO code (en/es/pt).
        number: Optional sub-page selector (issue, book, chapter).

    Returns:
        title, paragraphs[] (chapter/article titles in the TOC), source_url.
    """
    wol = _get_wol()
    try:
        url, html = await wol.get_publication_page(pub_code, number, language=language)
    except Exception as e:
        return {"error": str(e)}
    article = parse_article(html)
    return {
        "pub_code": pub_code,
        "language": language,
        "number": number,
        "title": article.title,
        "paragraphs": article.paragraphs,
        "references": article.references,
        "source_url": url,
    }


# ────────────────────────────────────────────────────────────────────────
# Tool: list_weblang_languages (Phase 2 — gap from original plan)
# ────────────────────────────────────────────────────────────────────────


@mcp.tool
async def list_weblang_languages(
    in_language_iso: str = "en",
) -> dict[str, Any]:
    """Alternate language list from www.jw.org/{iso}/languages/.

    Complements `list_languages` (which uses data.jw-api.org/mediator):
    the weblang endpoint returns more per-language fields (vernacular name,
    script, alternative spellings) and is updated less frequently.

    Args:
        in_language_iso: ISO code for the display-name language. 'en'
            returns English names; 'es' Spanish names.
    """
    from jw_core.clients.weblang import WeblangClient, WeblangError

    client = WeblangClient()
    try:
        langs = await client.list_languages(in_language_iso=in_language_iso)
    except WeblangError as e:
        return {"error": str(e)}
    finally:
        await client.aclose()
    return {
        "in_language_iso": in_language_iso,
        "count": len(langs),
        "languages": [lang.model_dump() for lang in langs],
    }


# ────────────────────────────────────────────────────────────────────────
# Entry point
# ────────────────────────────────────────────────────────────────────────


def main() -> None:
    """Run the MCP server over stdio."""
    logger.info("Starting jw-agent-toolkit MCP server")
    mcp.run()


if __name__ == "__main__":
    main()
