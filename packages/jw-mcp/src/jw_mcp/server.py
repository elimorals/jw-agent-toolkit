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
    public_talk_outline as public_talk_outline_agent,
)
from jw_agents import (
    research_topic as research_topic_agent,
)
from jw_agents import (
    verse_explainer as verse_explainer_agent,
)
from jw_agents import (
    workbook_helper as workbook_helper_agent,
)
from jw_agents.audio_helper import (
    read_article_aloud as _read_article_aloud,
)
from jw_agents.audio_helper import (
    read_verse_aloud as _read_verse_aloud,
)
from jw_agents.audio_helper import (
    search_broadcasting as _search_broadcasting,
)
from jw_agents.conversation_assistant import conversation_assistant as conversation_assistant_agent
from jw_agents.presentation_builder import list_audiences as _list_audiences
from jw_agents.presentation_builder import presentation_builder as presentation_builder_agent
from jw_agents.reverse_citation_lookup import reverse_citation_lookup as reverse_citation_lookup_agent
from jw_agents.revisit_tracker import Revisit, RevisitStore, plan_next_visit
from jw_agents.news_monitor import news_monitor as news_monitor_agent
from jw_agents.study_conductor import prepare_lesson as prepare_lesson_agent
from jw_core.audio.broadcasting import BroadcastingIndex, index_vtt_file
from jw_core.audio.tts import list_tts_providers
from jw_core.clients.cdn import CDNClient
from jw_core.clients.mediator import MediatorClient
from jw_core.clients.pub_media import PubMediaClient, PubMediaError
from jw_core.clients.topic_index import TopicIndexClient, TopicIndexError
from jw_core.clients.wol import WOLClient
from jw_core.data.objections import list_objections
from jw_core.integrations.jw_library import (
    JWLibraryError,
    build_bible_url,
    build_publication_url,
    build_url_for_ref,
    detect_platform,
    open_jw_library,
)
from jw_core.integrations.jw_library_local import (
    MacOSFullDiskAccessError,
    check_macos_full_disk_access,
    inspect_local_jw_library,
    read_macos_userdata,
)
from jw_core.integrations.jw_library_sync import sync_backup_to_rag
from jw_core.integrations.markdown import (
    convert_jw_links_in_text,
    linkify_markdown,
    render_verse_block,
)
from jw_core.integrations.meps_catalog import MepsCatalog
from jw_core.integrations.obsidian_vault import (
    export_backup_to_vault,
    index_vault_to_rag,
)
from datetime import date as _date
from jw_core.languages import get_language
from jw_core.ministry.exporters import render_csv, render_markdown
from jw_core.ministry.field_report import (
    FieldReportStore,
    HoursEntry,
    StudyEntry,
    aggregate_monthly_report,
)
from jw_core.parsers.article import parse_article
from jw_core.parsers.daily_text import parse_daily_text
from jw_core.parsers.epub import parse_epub
from jw_core.parsers.jw_library_backup import (
    JWLibraryBackupError,
    notes_for_chapter,
    parse_jw_library_backup,
)
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
# Tool: workbook_helper (Phase 11 — weekly meeting)
# ────────────────────────────────────────────────────────────────────────


@mcp.tool
async def workbook_helper(
    target_date: str = "",
    language: str = "en",
    include_watchtower: bool = True,
    include_comments: bool = True,
    comments_per_paragraph: int = 1,
) -> dict[str, Any]:
    """Discover the meeting workbook + Watchtower study for a given week.

    Args:
        target_date: ISO `YYYY-MM-DD` (empty = today).
        language: ISO code (en/es/pt).
        include_watchtower: Also pull the WT Study article (paragraphs +
            questions + scripture refs).
        include_comments: Synthesise short comment scripts per paragraph.
        comments_per_paragraph: 1..3 angles per paragraph.

    Returns the agent envelope with workbook assignments and (optionally)
    WT study paragraphs + comment suggestions.
    """
    result = await workbook_helper_agent(
        target_date or None,
        language=language,
        include_watchtower=include_watchtower,
        include_comments=include_comments,
        comments_per_paragraph=comments_per_paragraph,
        wol=_get_wol(),
    )
    return result.to_dict()


# ────────────────────────────────────────────────────────────────────────
# Tool: public_talk_outline (Phase 11)
# ────────────────────────────────────────────────────────────────────────


@mcp.tool
async def public_talk_outline(
    theme: str,
    language: str = "E",
    duration_minutes: int = 30,
    main_points: int = 3,
    illustration_top_k: int = 4,
) -> dict[str, Any]:
    """Build a public-discourse outline for a theme phrase or theme scripture.

    Uses topic_index + CDN search to harvest doctrinal anchors + recent
    publications' illustrations. The outline skeleton is rendered in the
    target language; every finding carries a wol.jw.org citation.
    """
    result = await public_talk_outline_agent(
        theme,
        language=language,
        duration_minutes=duration_minutes,
        main_points=main_points,
        illustration_top_k=illustration_top_k,
        topic=_get_topic(),
        cdn=_get_cdn(),
        wol=_get_wol(),
    )
    return result.to_dict()


# ────────────────────────────────────────────────────────────────────────
# Tool: conversation_assistant (Phase 12 — ministry)
# ────────────────────────────────────────────────────────────────────────


@mcp.tool
async def conversation_assistant(
    text: str,
    language: str = "E",
    max_subheadings: int = 6,
) -> dict[str, Any]:
    """Match text against common objections and return authoritative answers.

    Uses the objection catalog (Trinity, hell, soul, blood, etc.) + topic
    index + scripture anchors. The result is a structured envelope the
    LLM can synthesise into a respectful, sourced reply.
    """
    result = await conversation_assistant_agent(
        text,
        language=language,
        topic=_get_topic(),
        cdn=_get_cdn(),
        wol=_get_wol(),
        max_subheadings=max_subheadings,
    )
    return result.to_dict()


@mcp.tool
def list_known_objections(language: str = "en") -> dict[str, Any]:
    """Return the catalog of common objections recognized by the assistant."""
    return {"count": len(list_objections(language)), "objections": list_objections(language)}


# ────────────────────────────────────────────────────────────────────────
# Tool: presentation_builder (Phase 12)
# ────────────────────────────────────────────────────────────────────────


@mcp.tool
async def presentation_builder(
    audience: str,
    language: str = "E",
    topic_overrides: list[str] | None = None,
) -> dict[str, Any]:
    """Scaffold a witnessing presentation for an audience profile.

    Supported audience keys: catholic, evangelical, atheist, muslim, young,
    struggling_grief. The result includes opening questions, common ground,
    anchor scriptures + topic-index anchors, and tone notes.
    """
    result = await presentation_builder_agent(
        audience,
        language=language,
        topic_overrides=topic_overrides,
        topic=_get_topic(),
    )
    return result.to_dict()


@mcp.tool
def list_audiences(language: str = "en") -> dict[str, Any]:
    """List supported audience profiles for `presentation_builder`."""
    return {"count": len(_list_audiences(language)), "audiences": _list_audiences(language)}


# ────────────────────────────────────────────────────────────────────────
# Tool: reverse_citation_lookup (Phase 12)
# ────────────────────────────────────────────────────────────────────────


@mcp.tool
async def reverse_citation_lookup(
    quote: str,
    language: str = "E",
    top_n: int = 8,
    min_confidence: float = 0.4,
) -> dict[str, Any]:
    """Given a quote, find the JW publication it came from.

    Evaluates the top N CDN search hits and keeps matches whose
    bigram overlap exceeds `min_confidence`.
    """
    result = await reverse_citation_lookup_agent(
        quote,
        language=language,
        top_n=top_n,
        min_confidence=min_confidence,
        cdn=_get_cdn(),
        wol=_get_wol(),
    )
    return result.to_dict()


# ────────────────────────────────────────────────────────────────────────
# Tools: revisit tracker (Phase 12 — local only, never synced)
# ────────────────────────────────────────────────────────────────────────


def _get_revisit_store() -> RevisitStore:
    return RevisitStore()


@mcp.tool
def revisit_upsert(
    interest_id: str,
    name_alias: str = "(anonymous)",
    location_hint: str = "",
    language: str = "en",
    last_topic: str = "",
    notes: str = "",
    next_visit_iso: str = "",
    tags: list[str] | None = None,
) -> dict[str, Any]:
    """Create or update a revisit note in the local SQLite store.

    PRIVACY: data lives on this device only (~/.jw-agent-toolkit/ministry.db).
    Override via `JW_MINISTRY_DB`. No network calls.
    """
    rev = Revisit(
        interest_id=interest_id,
        name_alias=name_alias,
        location_hint=location_hint,
        language=language,
        last_topic=last_topic,
        notes=notes,
        next_visit_iso=next_visit_iso,
        tags=tags or [],
    )
    with _get_revisit_store() as store:
        saved = store.upsert(rev)
    return {"interest_id": saved.interest_id, "updated_at_unix": saved.updated_at_unix}


@mcp.tool
def revisit_list(language: str = "") -> dict[str, Any]:
    """List all revisits (optionally filtered by language)."""
    with _get_revisit_store() as store:
        items = store.list_all(language=language or None)
    return {"count": len(items), "revisits": [i.to_row() for i in items]}


@mcp.tool
def revisit_plan(interest_id: str, language: str = "en") -> dict[str, Any]:
    """Build a checklist for the next visit to `interest_id`."""
    with _get_revisit_store() as store:
        rev = store.get(interest_id)
    if rev is None:
        return {"error": f"No revisit with id {interest_id!r}"}
    return plan_next_visit(rev, language=language)


@mcp.tool
def revisit_due(on_or_before: str) -> dict[str, Any]:
    """Return revisits whose `next_visit_iso` is on or before `on_or_before` (YYYY-MM-DD)."""
    with _get_revisit_store() as store:
        items = store.due(on_or_before=on_or_before)
    return {"count": len(items), "revisits": [i.to_row() for i in items]}


@mcp.tool
def revisit_delete(interest_id: str) -> dict[str, Any]:
    """Delete a stored revisit note by `interest_id`. Returns the deletion status."""
    with _get_revisit_store() as store:
        ok = store.delete(interest_id)
    return {"interest_id": interest_id, "deleted": ok}


# ────────────────────────────────────────────────────────────────────────
# Tools: audio (Phase 13)
# ────────────────────────────────────────────────────────────────────────


@mcp.tool
def list_tts_engines() -> dict[str, Any]:
    """List available TTS providers on this machine (system/edge/piper)."""
    items = list_tts_providers()
    return {"count": len(items), "providers": items}


@mcp.tool
async def read_verse_aloud(
    book_num: int,
    chapter: int,
    verse: int,
    output_path: str,
    language: str = "en",
    provider: str = "",
    voice: str = "",
) -> dict[str, Any]:
    """Synthesise a Bible verse to an audio file using the chosen TTS provider.

    The file is written to `output_path`. Returns the path + verse metadata.
    """
    result = await _read_verse_aloud(
        book_num,
        chapter,
        verse,
        language=language,
        output_path=output_path,
        provider=provider or None,
        voice=voice or None,
        wol=_get_wol(),
    )
    return result.to_dict()


@mcp.tool
async def read_article_aloud(
    url: str,
    output_path: str,
    language: str = "en",
    max_paragraphs: int = 5,
    provider: str = "",
    voice: str = "",
) -> dict[str, Any]:
    """Synthesise the first N paragraphs of an article to an audio file."""
    result = await _read_article_aloud(
        url,
        output_path=output_path,
        language=language,
        max_paragraphs=max_paragraphs,
        provider=provider or None,
        voice=voice or None,
        wol=_get_wol(),
    )
    return result.to_dict()


@mcp.tool
def search_broadcasting(query: str, language: str = "", top_k: int = 10) -> dict[str, Any]:
    """Full-text search over the local JW Broadcasting subtitle index."""
    result = _search_broadcasting(query, language=language or None, top_k=top_k)
    return result.to_dict()


@mcp.tool
def index_broadcasting_vtt(
    vtt_path: str,
    video_id: str,
    title: str = "",
    language: str = "en",
    source_url: str = "",
) -> dict[str, Any]:
    """Add a single WebVTT subtitle file to the local broadcasting index."""
    with BroadcastingIndex() as idx:
        n = index_vtt_file(
            idx,
            vtt_path,
            video_id=video_id,
            title=title,
            language=language,
            source_url=source_url,
        )
        stats = idx.stats()
    return {"video_id": video_id, "segments_added": n, "index_stats": stats}


# ────────────────────────────────────────────────────────────────────────
# Tools: JW Library backup parsing (Phase 19 — integrations)
# ────────────────────────────────────────────────────────────────────────


@mcp.tool
def import_jw_library_backup(backup_path: str) -> dict[str, Any]:
    """Read a `.jwlibrary` archive (User Data Backup) and report a summary.

    Returns the manifest (creation date, device name, schema version) and
    counts per category. To project the actual notes, call
    `list_user_notes`. To index them into RAG, call `ingest_user_notes`.

    The archive is read in memory; the live JW Library DB is never touched.
    """
    try:
        backup = parse_jw_library_backup(backup_path)
    except JWLibraryBackupError as e:
        return {"error": str(e)}
    return {
        "source_path": backup.source_path,
        "manifest": backup.manifest.model_dump(),
        "counts": backup.counts,
    }


@mcp.tool
def list_user_notes(
    backup_path: str,
    book_num: int | None = None,
    chapter: int | None = None,
    tag: str = "",
    limit: int = 50,
) -> dict[str, Any]:
    """Project user notes from a `.jwlibrary` backup, optionally filtered.

    Args:
        backup_path: Path to the `.jwlibrary` archive.
        book_num: When set together with `chapter`, restrict to notes
            addressing that Bible chapter.
        chapter: Required if `book_num` is set.
        tag: Filter to notes that carry this tag name (e.g. 'Favorite').
        limit: Cap the result count. 0 = unlimited.
    """
    try:
        backup = parse_jw_library_backup(backup_path)
    except JWLibraryBackupError as e:
        return {"error": str(e)}
    items = backup.notes
    if book_num is not None and chapter is not None:
        items = notes_for_chapter(backup, book_num=book_num, chapter=chapter)
    if tag:
        items = [n for n in items if tag in n.tags]
    if limit and limit > 0:
        items = items[:limit]
    return {
        "source_path": backup.source_path,
        "filters": {
            "book_num": book_num,
            "chapter": chapter,
            "tag": tag or None,
            "limit": limit,
        },
        "count": len(items),
        "notes": [n.model_dump() for n in items],
    }


@mcp.tool
def sync_jw_library_backup(
    backup_path: str,
    state_path: str = "",
    include_bookmarks: bool = True,
    include_input_fields: bool = True,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Incremental sync of a `.jwlibrary` backup into the local RAG store.

    Diffs the backup against a sidecar state file and applies only the
    delta: new notes are added, modified notes get their old chunks
    evicted and re-indexed, deleted notes are removed from the store.
    A second call against the same backup is a no-op.

    The state file holds entries keyed by `manifest.hash` so the same
    sidecar can track multiple backups (e.g. iPhone + iPad). Default
    location: `<rag-store>/jw_library_sync.json`.

    Args:
        backup_path: Path to the `.jwlibrary` archive.
        state_path: Where to keep the sidecar JSON. Empty = default.
        include_bookmarks: Sync bookmark snippets too.
        include_input_fields: Sync meeting workbook answers too.
        dry_run: Compute the plan without mutating anything.
    """
    store = _get_rag_store()
    try:
        report = sync_backup_to_rag(
            backup_path,
            store,
            state_path=state_path or None,
            include_bookmarks=include_bookmarks,
            include_input_fields=include_input_fields,
            dry_run=dry_run,
        )
    except JWLibraryBackupError as e:
        return {"error": str(e)}
    if not dry_run:
        store.save()
    return report.to_dict()


@mcp.tool
def ingest_user_notes(
    backup_path: str,
    include_bookmarks: bool = True,
    include_input_fields: bool = True,
) -> dict[str, Any]:
    """Ingest notes / bookmarks / input-field answers from a backup into RAG.

    After this call, `semantic_search` can surface the user's own writing
    alongside the public corpus. Chunks are tagged with `kind='user_note'`,
    `'user_bookmark'`, or `'user_input'` so callers can filter.
    """
    from jw_rag.ingest import ingest_jw_library_backup as _ingest_backup

    store = _get_rag_store()
    try:
        total = _ingest_backup(
            store,
            backup_path,
            include_bookmarks=include_bookmarks,
            include_input_fields=include_input_fields,
        )
    except JWLibraryBackupError as e:
        return {"error": str(e)}
    store.save()
    return {
        "backup_path": backup_path,
        "include_bookmarks": include_bookmarks,
        "include_input_fields": include_input_fields,
        "chunks_added": total,
        "store_total": store.count,
    }


# ────────────────────────────────────────────────────────────────────────
# Tools: JW Library deep linking (Phase 19 — integrations)
# ────────────────────────────────────────────────────────────────────────


@mcp.tool
def open_in_jw_library(
    reference: str = "",
    book_num: int | None = None,
    chapter: int | None = None,
    verse_start: int | None = None,
    verse_end: int | None = None,
    end_chapter: int | None = None,
    docid: int | None = None,
    paragraph: int | None = None,
    language: str = "",
    dry_run: bool = True,
) -> dict[str, Any]:
    """Build a `jwlibrary://` deep link and (optionally) open it in the app.

    Two modes:

      1. **Bible reference** — pass `reference` (e.g. "Juan 3:16-18") OR the
         numeric form `book_num` + `chapter` + `verse_start` (+ `verse_end`
         + `end_chapter` for ranges).
      2. **Publication** — pass `docid` (and optionally `paragraph`). Derive
         `docid` from a downloaded `.jwpub` via `inspect_jwpub_metadata`.

    `dry_run=True` (default) is safe for chat: it returns the URL without
    launching anything. Set `dry_run=False` to spawn the OS URL handler
    (`open` on macOS, `cmd /c start` on Windows, `xdg-open` on Linux).
    `language` accepts ISO ('en', 'es', 'pt') or JW codes ('E', 'S', 'T').
    """
    try:
        if docid is not None:
            url = build_publication_url(
                docid,
                paragraph=paragraph,
                wtlocale=language or None,
            )
        elif book_num is not None and chapter is not None:
            url = build_bible_url(
                book_num,
                chapter,
                verse_start,
                verse_end=verse_end,
                end_chapter=end_chapter,
                wtlocale=language or None,
            )
        elif reference:
            ref = parse_reference(reference)
            if ref is None:
                return {"error": f"No Bible reference detected in: {reference!r}"}
            url = build_url_for_ref(ref, wtlocale=language or None)
        else:
            return {"error": "Pass either `reference`, `book_num`+`chapter`, or `docid`."}
        result = open_jw_library(url, dry_run=dry_run)
    except JWLibraryError as e:
        return {"error": str(e)}
    return {**result, "platform_detected": detect_platform()}


# ────────────────────────────────────────────────────────────────────────
# Tools: MEPS docid catalog (Phase 19 — integrations)
# ────────────────────────────────────────────────────────────────────────


@mcp.tool
def register_jwpub_in_catalog(jwpub_path: str, catalog_db: str = "") -> dict[str, Any]:
    """Index a `.jwpub` file's metadata into the local MEPS docid catalog.

    Parses the publication's manifest (no decryption — cheap) and upserts
    every Document row so future deep links can resolve a publication
    symbol (`bh`, `w24`, `lff`) into a MEPS `docid`.

    Args:
        jwpub_path: Path to a downloaded `.jwpub`.
        catalog_db: Override the catalog DB path. Empty = default
            (~/.jw-agent-toolkit/meps_catalog.db).
    """
    try:
        with MepsCatalog(db_path=catalog_db or None) as cat:
            result = cat.index_jwpub(jwpub_path)
            result["stats"] = cat.stats()
        return result
    except Exception as e:
        return {"error": str(e)}


@mcp.tool
def find_publication_in_catalog(
    pub_code: str = "",
    document_id: int | None = None,
    meps_document_id: int | None = None,
    language_index: int | None = None,
    chapter_number: int | None = None,
    limit: int = 25,
    catalog_db: str = "",
) -> dict[str, Any]:
    """Query the MEPS catalog by any combination of pub_code/docid/chapter.

    Returns matching publications + documents. Useful for the LLM to
    discover which publication contains a given chapter or which docid
    corresponds to a publication symbol before building a deep link.
    """
    try:
        with MepsCatalog(db_path=catalog_db or None) as cat:
            docs = cat.find_documents(
                pub_code=pub_code or None,
                document_id=document_id,
                meps_document_id=meps_document_id,
                language_index=language_index,
                chapter_number=chapter_number,
                limit=limit,
            )
            pubs = cat.list_publications(
                pub_code=pub_code or None,
                language_index=language_index,
            )
            return {
                "publications": [p.to_dict() for p in pubs],
                "documents": [d.to_dict() for d in docs],
                "stats": cat.stats(),
            }
    except Exception as e:
        return {"error": str(e)}


@mcp.tool
def open_publication_by_symbol(
    pub_code: str,
    chapter_number: int | None = None,
    paragraph: int | None = None,
    language_index: int | None = None,
    language: str = "",
    dry_run: bool = True,
    catalog_db: str = "",
) -> dict[str, Any]:
    """Build (and optionally dispatch) a `jwlibrary://` deep link by symbol.

    Resolves `pub_code` (+ optional `chapter_number`) via the local MEPS
    catalog, then builds `jwlibrary:///finder?docid=N&par=P`. Run
    `register_jwpub_in_catalog` on each `.jwpub` you want addressable by
    symbol before calling this.

    Args:
        pub_code: Publication symbol (e.g. "bh", "lff", "w24").
        chapter_number: Optional — restrict to a specific chapter.
        paragraph: Optional — paragraph anchor inside the document.
        language_index: MEPS language index (0 = English). When omitted,
            falls back to English if available.
        language: ISO/JW locale tag for the `wtlocale=` parameter.
        dry_run: True (default) returns the URL without opening anything.
        catalog_db: Override catalog DB path.
    """
    try:
        with MepsCatalog(db_path=catalog_db or None) as cat:
            doc = cat.resolve_docid(
                pub_code,
                chapter_number=chapter_number,
                language_index=language_index,
            )
        if doc is None:
            return {
                "error": (
                    f"No document found for pub_code={pub_code!r} "
                    f"(chapter={chapter_number}, language_index={language_index}). "
                    "Register the matching .jwpub via register_jwpub_in_catalog first."
                )
            }
        url = build_publication_url(
            doc.document_id,
            paragraph=paragraph,
            wtlocale=language or None,
        )
        result = open_jw_library(url, dry_run=dry_run)
    except JWLibraryError as e:
        return {"error": str(e)}
    return {
        "resolved": doc.to_dict(),
        "platform_detected": detect_platform(),
        **result,
    }


# ────────────────────────────────────────────────────────────────────────
# Tool: inspect_local_jw_library (Phase 19 — integrations)
# ────────────────────────────────────────────────────────────────────────


@mcp.tool
def check_jw_library_full_disk_access() -> dict[str, Any]:
    """Check whether this process can read the macOS JW Library sandbox.

    macOS apps under the Mac App Store sandbox are unreadable by third-
    party processes unless the host (terminal / Claude Desktop / VS Code)
    has been granted Full Disk Access in System Settings. This tool
    probes the container path with `os.scandir` and reports the outcome
    plus actionable instructions.
    """
    return check_macos_full_disk_access()


@mcp.tool
def read_jw_library_live_userdata(book_num: int | None = None, chapter: int | None = None, limit: int = 50) -> dict[str, Any]:
    """Load notes from the live macOS sandbox container (requires FDA).

    Same shape as `list_user_notes`, but reads the **live** `userData.db`
    inside the container — no backup export needed. Fails fast with a
    clear instruction if Full Disk Access has not been granted.
    """
    try:
        backup = read_macos_userdata()
    except MacOSFullDiskAccessError as e:
        return {"error": str(e), "needs_full_disk_access": True}
    notes = backup.notes
    if book_num is not None and chapter is not None:
        from jw_core.parsers.jw_library_backup import notes_for_chapter as _filter

        notes = _filter(backup, book_num=book_num, chapter=chapter)
    if limit and limit > 0:
        notes = notes[:limit]
    return {
        "source_path": backup.source_path,
        "manifest": backup.manifest.model_dump(),
        "counts": backup.counts,
        "filters": {"book_num": book_num, "chapter": chapter, "limit": limit},
        "notes": [n.model_dump() for n in notes],
    }


@mcp.tool
def inspect_local_jw_library_tool(force: bool = False) -> dict[str, Any]:
    """Inspect the JW Library app installed on this machine (read-only).

    Returns the platform, whether the app was detected, the publication
    catalog (Windows only — the UWP package's `publications.db`), and
    actionable reasons / suggestions when something is unsupported.

    Opt-in: by default the inspector refuses unless `JW_LIBRARY_LOCAL_READ=1`
    is set in the environment. Pass `force=True` to bypass that check.

    Platform behavior:
      - Windows: reads `publications.db` from LocalAppData and reports the
        userData.db path if present.
      - macOS: app runs in the App Store sandbox; we never open its files.
        The tool reports the install path and asks for a `.jwlibrary`
        backup instead.
      - Linux: not supported (no native build).
    """
    return inspect_local_jw_library(force=force).to_dict()


# ────────────────────────────────────────────────────────────────────────
# Tools: Markdown utilities (Phase 20 — Obsidian bridge)
# ────────────────────────────────────────────────────────────────────────


@mcp.tool
def linkify_markdown_text(
    text: str,
    language: str = "en",
    length: str = "medium",
    wtlocale: str = "",
) -> dict[str, Any]:
    r"""Wrap every Bible reference in `text` as a `jwlibrary://` markdown link.

    Skips refs already inside `[…](…)` links, inside `\`inline code\``, and
    inside fenced code blocks. Respects 17 locales (English, Spanish,
    Portuguese, French, German, Italian, Russian, Japanese, Korean,
    Czech, Croatian, Danish, Dutch, Finnish, Tagalog, Vietnamese,
    Cibemba) so the user can write in any of them.

    Args:
        text: Source markdown.
        language: ISO code that drives the rendered label.
        length: 'short' / 'medium' / 'long'.
        wtlocale: Optional override for the `wtlocale=` URL parameter.
            Empty string means "match `language`".
    """
    result = linkify_markdown(
        text,
        language=language,
        length=length,  # type: ignore[arg-type]
        wtlocale=wtlocale or None,
    )
    return result.to_dict()


@mcp.tool
def convert_jw_links_in_markdown(
    text: str,
    kind: str = "all",
    wtlocale: str = "",
) -> dict[str, Any]:
    """Rewrite legacy `jwpub://b/...` / `jwpub://p/...` URLs to `jwlibrary://`.

    Useful for refreshing old notes that still contain the legacy
    Watchtower Library / Logos scheme. `kind` filters which subset to
    touch ('bible', 'publication', 'all').
    """
    stats = convert_jw_links_in_text(
        text,
        kind=kind,  # type: ignore[arg-type]
        wtlocale=wtlocale or None,
    )
    return stats.to_dict()


@mcp.tool
async def get_verse_as_markdown(
    reference: str,
    language: str = "en",
    template: str = "callout",
    length: str = "medium",
    publication: str = "nwtsty",
    include_text: bool = True,
) -> dict[str, Any]:
    """Fetch a verse from wol.jw.org and render it as ready-to-paste markdown.

    Templates: 'plain' / 'link' / 'blockquote' / 'callout' /
    'callout-collapsed'. The 'callout' templates use Obsidian's `[!quote]`
    callout syntax.
    """
    ref = parse_reference(reference)
    if ref is None:
        return {"error": f"No Bible reference detected in: {reference!r}"}
    verse_text = ""
    source_url = ""
    if include_text and ref.verse_start is not None:
        wol = _get_wol()
        url, html = await wol.get_bible_chapter(
            ref.book_num,
            ref.chapter,
            language=language,
            publication=publication,
        )
        v = _get_verse_from_html(html, ref.book_num, ref.chapter, ref.verse_start, language=language)
        verse_text = v.text if v else ""
        source_url = url
    md = render_verse_block(
        ref,
        verse_text,
        template=template,  # type: ignore[arg-type]
        length=length,  # type: ignore[arg-type]
        language=language,
    )
    return {
        "markdown": md,
        "reference": ref.display(),
        "language": language,
        "source_url": source_url,
    }


# ────────────────────────────────────────────────────────────────────────
# Tools: Obsidian vault sync (Phase 20)
# ────────────────────────────────────────────────────────────────────────


@mcp.tool
def index_obsidian_vault(
    vault_root: str,
    state_path: str = "",
    require_tag: str = "",
    glob: str = "**/*.md",
    min_chars: int = 16,
) -> dict[str, Any]:
    """Incremental sync an Obsidian vault into the local RAG store.

    First call indexes every `.md`. Subsequent calls re-use the sidecar
    state to only process new / modified / deleted files (mtime +
    content_hash). The store ends up holding `vault_note` chunks
    alongside any JW.org content already indexed.

    `require_tag` filters to notes whose frontmatter `tags` list
    contains the given value (e.g. 'ministry').
    """
    store = _get_rag_store()
    try:
        report = index_vault_to_rag(
            vault_root,
            store,
            state_path=state_path or None,
            glob=glob,
            require_tag=require_tag or None,
            min_chars=min_chars,
        )
    except FileNotFoundError as e:
        return {"error": str(e)}
    store.save()
    return report.to_dict()


@mcp.tool
def export_jw_library_backup_to_vault(
    backup_path: str,
    vault_dir: str,
    template: str = "callout",
    length: str = "medium",
    language: str = "en",
    subdir: str = "JW Library",
    overwrite: bool = False,
) -> dict[str, Any]:
    """Write one `.md` per JW Library note into an Obsidian vault directory.

    Bible-anchored notes go under `<vault>/<subdir>/bible/BB/chapter-CCC/`.
    Publication-anchored notes go under `<vault>/<subdir>/publications/<key>/`.
    Each file has Obsidian-friendly frontmatter (book, chapter, tags,
    created, last_modified) plus a deep-link callout to JW Library.
    """
    try:
        report = export_backup_to_vault(
            backup_path,
            vault_dir,
            template=template,  # type: ignore[arg-type]
            length=length,  # type: ignore[arg-type]
            language=language,
            subdir=subdir,
            overwrite=overwrite,
        )
    except Exception as e:
        return {"error": str(e)}
    return report.to_dict()


# ────────────────────────────────────────────────────────────────────────
# Fase 23: Citation integrity validator
# ────────────────────────────────────────────────────────────────────────

import asyncio as _asyncio  # noqa: E402
import os as _os  # noqa: E402
from typing import Any as _Any  # noqa: E402

from jw_core.citations import CitationValidator as _CitationValidator  # noqa: E402
from jw_core.integrations.meps_catalog import MepsCatalog as _MepsCatalog  # noqa: E402


@mcp.tool
def validate_citations(
    urls: list[str] | None = None,
    agent_output: dict | None = None,
    live: bool = False,
    check_drift: bool = False,
) -> dict:
    """Validate that wol.jw.org URLs from an agent resolve and map cleanly.

    Pass exactly one of `urls` or `agent_output`. The latter must be the
    serialized AgentResult shape ({"findings": [{"metadata": {...}}]}).

    Modes:
      - default (offline): MEPS docId↔pub_code lookup against the local catalog.
      - live=True: also HTTP-resolve every URL. Requires env JW_CITATIONS_LIVE=1.
      - check_drift=True (implies live): compare HTML shape against committed snapshots.

    Returns the CitationReport as a dict.
    """

    if (urls is None) == (agent_output is None):
        return {"error": "pass exactly one of urls= or agent_output="}

    if live and _os.environ.get("JW_CITATIONS_LIVE", "").lower() not in {"1", "true", "yes"}:
        return {
            "error": "live=True requires env JW_CITATIONS_LIVE=1 to authorize network access"
        }

    async def _run() -> dict:
        catalog = _MepsCatalog()
        kwargs: dict[str, _Any] = {"catalog": catalog}

        client = None
        if live:
            import httpx  # local import — keeps cold-start light
            from jw_core.citations.validator import httpx_fetcher

            client = httpx.AsyncClient(timeout=30.0, follow_redirects=True)
            kwargs["fetcher"] = httpx_fetcher(client)

        if check_drift:
            from pathlib import Path

            snaps = Path("packages/jw-eval/fixtures/wol_snapshots")
            if snaps.exists():
                kwargs["snapshots_root"] = snaps

        v = _CitationValidator(**kwargs)
        try:
            mode = "live+drift" if (live and check_drift) else ("live" if live else "structural")
            if urls is not None:
                report = await v.validate_urls(urls, mode=mode)
            else:
                report = await v.validate_agent_output(agent_output, mode=mode)
            return report.model_dump(mode="json")
        finally:
            if client is not None:
                await client.aclose()

    return _asyncio.run(_run())


# ────────────────────────────────────────────────────────────────────────
# Study conductor tools (Fase 24)
# ────────────────────────────────────────────────────────────────────────


@mcp.tool
def prepare_lesson(
    pub_code: str,
    chapter: int,
    language: str = "es",
) -> dict[str, Any]:
    """Prepare a study-book lesson: anticipation questions + key verses + topics.

    Args:
        pub_code: Publication code (e.g. "lff" for Enjoy Life Forever!).
        chapter: 1-based chapter number.
        language: ISO code (es/en/pt/…). Falls back to English for unknown.
    """

    try:
        result = prepare_lesson_agent(pub_code, chapter=chapter, language=language)
    except Exception as e:  # noqa: BLE001
        return {"error": str(e)}
    return result.to_dict()


# Student progress (encrypted-at-rest) tools ------------------------------

import os as _os_study
from datetime import datetime as _dt_study, timezone as _tz_study

from jw_agents.study_progress import (
    GoalKind as _GoalKind,
    LessonRow as _LessonRow,
    LessonStatus as _LessonStatus,
    StudentGoal as _StudentGoal,
    StudentProgressStore as _StudentProgressStore,
    default_salt_path as _default_salt_path,
    derive_encryptor_for_passphrase as _derive_enc,
    set_goal_for_student as _set_goal_for_student,
)


def _study_store() -> _StudentProgressStore | dict[str, str]:
    passphrase = _os_study.getenv("JW_STUDY_PASSPHRASE")
    if not passphrase:
        return {"error": "JW_STUDY_PASSPHRASE not set"}
    enc = _derive_enc(passphrase, salt_path=_default_salt_path())
    return _StudentProgressStore(encryptor=enc)


@mcp.tool
def log_student_progress(
    student_id: str,
    book_pub: str,
    lesson: int,
    status: str = "in_progress",
    note: str = "",
    goals: list[str] | None = None,
    target_iso: str | None = None,
) -> dict[str, Any]:
    """Record progress for (student, book, lesson). Notes encrypted at rest."""

    store_or_err = _study_store()
    if isinstance(store_or_err, dict):
        return store_or_err
    store = store_or_err

    try:
        now = _dt_study.now(_tz_study.utc).isoformat()
        row = _LessonRow(
            student_id=student_id, book_pub=book_pub, lesson=lesson,
            status=_LessonStatus(status), notes=note,
            updated_at_iso=now,
            started_at_iso=now if status == "in_progress" else None,
            completed_at_iso=now if status == "completed" else None,
            goals=[
                _StudentGoal(kind=_GoalKind(g), set_at_iso=now,
                              target_iso=(target_iso if g == "baptism" else None))
                for g in (goals or [])
            ],
            baptism_target_iso=(target_iso if goals and "baptism" in goals else None),
        )
        saved = store.upsert(row)
        return {"row": saved.model_dump(mode="json")}
    except Exception as e:  # noqa: BLE001
        return {"error": str(e)}


@mcp.tool
def list_student_lessons(
    student_id: str, book_pub: str | None = None,
) -> dict[str, Any]:
    """List a student's lessons (decrypted notes in-memory)."""

    store_or_err = _study_store()
    if isinstance(store_or_err, dict):
        return store_or_err
    store = store_or_err
    rows = store.list_for_student(student_id, book_pub=book_pub)
    return {"count": len(rows), "rows": [r.model_dump(mode="json") for r in rows]}


@mcp.tool
def set_student_goal(
    student_id: str,
    kind: str,
    book_pub: str = "lff",
    lesson: int = 1,
    target_iso: str | None = None,
    note: str = "",
) -> dict[str, Any]:
    """Append or replace a goal on a (student, book, lesson) row."""

    store_or_err = _study_store()
    if isinstance(store_or_err, dict):
        return store_or_err
    try:
        row = _set_goal_for_student(
            store_or_err, student_id, book_pub, lesson,
            kind=_GoalKind(kind), target_iso=target_iso, note=note,
        )
        return {"row": row.model_dump(mode="json")}
    except Exception as e:  # noqa: BLE001
        return {"error": str(e)}


@mcp.tool
async def news_digest(
    since: str | None = "last_run",
    languages: list[str] | None = None,
    channels: list[str] | None = None,
    update: bool = True,
) -> dict[str, Any]:
    """Run the news monitor and return the deterministic digest.

    Args:
        since: "last_run" (default), "epoch", or an ISO-8601 date (e.g.
            "2026-05-23"). Drives the human-facing "Ventana:" line of the
            digest; new/retired classification still uses the local seen-store.
        languages: ISO codes (en/es/pt/...). Default ["en","es","pt"].
        channels: subset of {"publications","broadcasting","programs"}.
            Default all three.
        update: when True, mark new items as seen and advance last_run.
            Use False from interactive sessions to preview without committing.

    Returns:
        Dict with `markdown` (ready to render), `stats`, `findings`,
        `warnings`, and `retired_items`. Cite each `findings[i].citation.url`.
    """

    try:
        result = await news_monitor_agent(
            since=since,
            languages=languages,
            channels=channels,
            update=update,
        )
    except ValueError as exc:
        return {"error": str(exc)}
    return result.to_dict() | {
        "markdown": result.metadata.get("markdown", ""),
        "stats": result.metadata.get("stats", {}),
        "since_resolved": result.metadata.get("since_resolved"),
    }


@mcp.tool
async def student_part_help(
    kind: str,
    topic_or_ref: str,
    language: str = "en",
    oratory_point: int | None = None,
    audience: str = "default",
) -> dict[str, Any]:
    """Compose a 4-section script for a Life-and-Ministry student assignment.

    `kind` is one of: bible_reading | starting_conversation | return_visit | bible_study.
    `topic_or_ref` may be a Bible reference, a free topic, or 'this week'.
    Returns the structured AgentResult serialized as dict — opening / body /
    transition / close findings plus metadata.time_target_seconds and
    metadata.oratory_point_applied.
    """
    from jw_agents import student_part_helper as _student_part_helper

    result = await _student_part_helper(
        kind=kind,
        topic_or_ref=topic_or_ref,
        language=language,
        oratory_point=oratory_point,
        audience=audience,
    )
    return result.to_dict()


# ---------------------------------------------------------------------------
# Phase 27 — Pioneer monthly report
# ---------------------------------------------------------------------------


@mcp.tool()
def field_log_hours(
    hours_decimal: float,
    date: str = "",
    tag: str | None = None,
    note: str = "",
) -> dict[str, Any]:
    """Registrar horas de servicio (local, cifrable). `date` ISO o vacío = hoy."""

    d = _date.fromisoformat(date) if date else _date.today()
    with FieldReportStore() as store:
        e = store.add_hours(
            HoursEntry(entry_id="", date=d, hours_decimal=hours_decimal, tag=tag, note=note)
        )
    return {"entry_id": e.entry_id, "date": e.date.isoformat(), "hours_decimal": e.hours_decimal, "tag": e.tag}


@mcp.tool()
def field_log_study(
    student_alias: str,
    started: str = "",
    closed: str = "",
    met_today: bool = False,
    note: str = "",
) -> dict[str, Any]:
    """Registrar, cerrar o marcar reunión de un curso bíblico (local, cifrable)."""

    with FieldReportStore() as store:
        if closed:
            n = store.close_study(student_id=student_alias, closed_at=_date.fromisoformat(closed))
            return {"closed_count": n, "student_alias": student_alias}
        s = store.upsert_study(
            StudyEntry(
                study_id="",
                student_id=student_alias,
                started_at=_date.fromisoformat(started) if started else _date.today(),
                note=note,
            )
        )
        if met_today:
            store.mark_met(student_id=student_alias, met_date=_date.today())
        return {
            "study_id": s.study_id,
            "student_alias": student_alias,
            "started_at": s.started_at.isoformat(),
            "met_today": met_today,
        }


@mcp.tool()
def field_monthly_report(
    month: str,
    include_revisits: bool = True,
    format: str = "json",
) -> dict[str, Any]:
    """Generar el informe mensual. ``format`` ∈ {json, markdown, csv}."""

    revisits = None
    if include_revisits:
        # Inline adapter — mirrors the CLI's _RevisitsAdapter.
        try:
            from jw_agents.revisit_tracker import RevisitStore as _RevisitStore
        except ImportError:
            _RevisitStore = None  # type: ignore[assignment]
        if _RevisitStore is not None:
            import datetime as _dt

            class _Adapter:
                def count_in_range(self, start: _date, end: _date) -> int:
                    try:
                        with _RevisitStore() as s:
                            rows = s.list_all()
                    except Exception:
                        return 0
                    n = 0
                    for r in rows:
                        ts = r.updated_at_unix or 0
                        if ts and start <= _dt.date.fromtimestamp(ts) <= end:
                            n += 1
                    return n

            revisits = _Adapter()

    with FieldReportStore() as store:
        report = aggregate_monthly_report(store, month, revisits=revisits)
    if format == "markdown":
        return {"format": "markdown", "body": render_markdown(report)}
    if format == "csv":
        return {"format": "csv", "body": render_csv(report)}
    return {"format": "json", **report.model_dump()}


# ---------------------------------------------------------------------------
# Phase 28 — Concordance (literal FTS5 search over local corpus)
# ---------------------------------------------------------------------------


from jw_mcp.tools.concordance import (  # noqa: E402
    concordance_build_index_tool as _concordance_build_index_tool,
    concordance_search_tool as _concordance_search_tool,
)


mcp.tool(name="concordance_build_index")(_concordance_build_index_tool)
mcp.tool(name="concordance_search")(_concordance_search_tool)


# ---------------------------------------------------------------------------
# Phase 29 — Letter composer (letter / phone / cart witnessing scaffolds)
# ---------------------------------------------------------------------------


from jw_agents.letter_composer import letter_composer as _letter_composer  # noqa: E402


@mcp.tool
async def compose_witnessing(
    kind: str,
    language: str = "es",
    topic: str = "",
    audience: str = "default",
    territory_hint: str | None = None,
    jw_link: str | None = None,
) -> dict[str, Any]:
    """Compose a witnessing scaffold (letter | phone | cart).

    Sections returned in order: opener, bridge, scripture, closing.
    Each carries a verifiable citation URL. No PII is persisted.

    Args:
        kind: One of 'letter', 'phone', 'cart'.
        language: 'en' | 'es' | 'pt'.
        topic: Free-form topic or question that the scaffold addresses.
        audience: 'default' | 'new' | 'religious' | 'atheist' | 'grieving' |
                  'young' | 'parents'.
        territory_hint: Optional cosmetic territory string for the opener.
        jw_link: Optional jw.org URL to use in the closing.
    """

    result = await _letter_composer(
        kind=kind,  # type: ignore[arg-type]
        language=language,
        topic_or_question=topic,
        audience=audience,
        territory_hint=territory_hint,
        jw_link=jw_link,
    )
    return result.to_dict()


# ────────────────────────────────────────────────────────────────────────
# Entry point
# ────────────────────────────────────────────────────────────────────────


def main() -> None:
    """Run the MCP server over stdio."""
    logger.info("Starting jw-agent-toolkit MCP server")
    mcp.run()


if __name__ == "__main__":
    main()
