"""REST API over the MCP toolset (Module 10).

Why: VISION.md asks for a REST API to drive bots (Telegram/WhatsApp/etc.)
without going through Claude Desktop. We expose the most-used agents
behind clean HTTP endpoints.

Run with:
    uv run uvicorn jw_mcp.rest_api:app --host 0.0.0.0 --port 8765

Endpoints (all return JSON):

    GET  /healthz
    POST /api/v1/verse        body: {"book_num":43,"chapter":3,"verse":16,"language":"en"}
    POST /api/v1/daily        body: {"language":"en","date":"YYYY-MM-DD"}
    POST /api/v1/search       body: {"query":"...","language":"E","limit":5}
    POST /api/v1/apologetics  body: {"question":"...","language":"E"}
    POST /api/v1/workbook     body: {"date":"YYYY-MM-DD","language":"en"}
    POST /api/v1/conversation body: {"text":"...","language":"E"}

Phase 20 (Obsidian bridge):

    POST /api/v1/linkify       body: {"text":"...","language":"es","length":"medium"}
    POST /api/v1/convert_links body: {"text":"...","kind":"all","wtlocale":""}
    POST /api/v1/verse_markdown body:{"reference":"Juan 3:16","template":"callout",
                                      "language":"es","length":"medium"}
    POST /api/v1/vault/index   body: {"vault_root":"/path","require_tag":""}
    POST /api/v1/vault/export  body: {"backup_path":"/p.jwlibrary",
                                      "vault_dir":"/vault","template":"callout"}
"""

from __future__ import annotations

import logging
from typing import Any

try:
    from fastapi import FastAPI
    from fastapi.middleware.cors import CORSMiddleware
    from pydantic import BaseModel
except ImportError as e:  # pragma: no cover
    raise ImportError("FastAPI is required for the REST API. `pip install fastapi uvicorn`") from e

from jw_agents import (
    apologetics as apologetics_agent,
)
from jw_agents.conversation_assistant import conversation_assistant
from jw_agents.workbook_helper import workbook_helper
from jw_core.clients.cdn import CDNClient
from jw_core.clients.wol import WOLClient
from jw_core.integrations.markdown import (
    convert_jw_links_in_text,
    linkify_markdown,
    render_verse_block,
)
from jw_core.integrations.obsidian_vault import (
    export_backup_to_vault,
    index_vault_to_rag,
)
from jw_core.languages import get_language
from jw_core.parsers.daily_text import parse_daily_text
from jw_core.parsers.reference import parse_reference
from jw_core.parsers.verse import get_verse

from jw_mcp.dashboard import router as dashboard_router

logger = logging.getLogger("jw-rest")
app = FastAPI(title="jw-agent-toolkit REST", version="0.1.0")

# Permissive CORS — bots may run anywhere; tighten for production.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)
app.include_router(dashboard_router)


# ── Shared clients ──────────────────────────────────────────────────────


_wol: WOLClient | None = None
_cdn: CDNClient | None = None


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


# ── Schemas ─────────────────────────────────────────────────────────────


class VerseRequest(BaseModel):
    book_num: int
    chapter: int
    verse: int
    language: str = "en"


class DailyTextRequest(BaseModel):
    language: str = "en"
    date: str = ""


class SearchRequest(BaseModel):
    query: str
    language: str = "E"
    limit: int = 5
    filter_type: str = "all"


class ApologeticsRequest(BaseModel):
    question: str
    language: str = "E"


class WorkbookRequest(BaseModel):
    date: str = ""
    language: str = "en"


class ConversationRequest(BaseModel):
    text: str
    language: str = "E"


# ── Phase 20: Obsidian-bridge schemas ──────────────────────────────────


class LinkifyRequest(BaseModel):
    text: str
    language: str = "en"
    length: str = "medium"  # short | medium | long
    wtlocale: str = ""


class ConvertLinksRequest(BaseModel):
    text: str
    kind: str = "all"  # bible | publication | all
    wtlocale: str = ""


class VerseMarkdownRequest(BaseModel):
    reference: str
    language: str = "en"
    template: str = "callout"  # plain | link | blockquote | callout | callout-collapsed
    length: str = "medium"
    publication: str = "nwtsty"
    include_text: bool = True


class VaultIndexRequest(BaseModel):
    vault_root: str
    state_path: str = ""
    require_tag: str = ""
    glob: str = "**/*.md"
    min_chars: int = 16


class VaultExportRequest(BaseModel):
    backup_path: str
    vault_dir: str
    template: str = "callout"
    length: str = "medium"
    language: str = "en"
    subdir: str = "JW Library"
    overwrite: bool = False


# ── Endpoints ───────────────────────────────────────────────────────────


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/v1/verse")
async def post_verse(req: VerseRequest) -> dict[str, Any]:
    url, html = await _get_wol().get_bible_chapter(req.book_num, req.chapter, language=req.language)
    v = get_verse(html, req.book_num, req.chapter, req.verse, language=req.language)
    if v is None:
        return {"error": "verse not found", "source_url": url}
    return {
        "book_num": v.book_num,
        "chapter": v.chapter,
        "verse": v.verse,
        "text": v.text,
        "language": v.language,
        "wol_url": v.wol_url(),
    }


@app.post("/api/v1/daily")
async def post_daily(req: DailyTextRequest) -> dict[str, Any]:
    wol = _get_wol()
    if req.date:
        url, html = await wol.get_daily_text_by_date(req.date, language=req.language)
    else:
        url, html = await wol.get_today_homepage(language=req.language)
    text = parse_daily_text(html)
    if text is None:
        return {"error": "could not parse", "source_url": url}
    return {
        "date": text.date,
        "scripture": text.scripture,
        "commentary": text.commentary,
        "source_url": url,
    }


@app.post("/api/v1/search")
async def post_search(req: SearchRequest) -> dict[str, Any]:
    lang = get_language(req.language)
    data = await _get_cdn().search(req.query, filter_type=req.filter_type, language=lang.jw_code, limit=req.limit)
    return {"query": req.query, "results": data}


@app.post("/api/v1/apologetics")
async def post_apologetics(req: ApologeticsRequest) -> dict[str, Any]:
    result = await apologetics_agent(
        req.question,
        language=req.language,
        cdn=_get_cdn(),
        wol=_get_wol(),
    )
    return result.to_dict()


@app.post("/api/v1/workbook")
async def post_workbook(req: WorkbookRequest) -> dict[str, Any]:
    result = await workbook_helper(
        req.date or None,
        language=req.language,
        wol=_get_wol(),
    )
    return result.to_dict()


@app.post("/api/v1/conversation")
async def post_conversation(req: ConversationRequest) -> dict[str, Any]:
    result = await conversation_assistant(req.text, language=req.language, cdn=_get_cdn(), wol=_get_wol())
    return result.to_dict()


# ── Phase 20 endpoints (Obsidian bridge) ───────────────────────────────


@app.post("/api/v1/linkify")
def post_linkify(req: LinkifyRequest) -> dict[str, Any]:
    """Convert every Bible reference in `text` to `jwlibrary://` markdown links.

    Skips existing links, code fences, and inline code. Returns the
    rewritten text plus counters.
    """
    result = linkify_markdown(
        req.text,
        language=req.language,
        length=req.length,  # type: ignore[arg-type]
        wtlocale=req.wtlocale or None,
    )
    return result.to_dict()


@app.post("/api/v1/convert_links")
def post_convert_links(req: ConvertLinksRequest) -> dict[str, Any]:
    """Rewrite legacy `jwpub://b/...` and `jwpub://p/...` links to `jwlibrary://`."""
    stats = convert_jw_links_in_text(
        req.text,
        kind=req.kind,  # type: ignore[arg-type]
        wtlocale=req.wtlocale or None,
    )
    return stats.to_dict()


@app.post("/api/v1/verse_markdown")
async def post_verse_markdown(req: VerseMarkdownRequest) -> dict[str, Any]:
    """Return a markdown block for the requested verse (link + optional quote)."""
    ref = parse_reference(req.reference)
    if ref is None:
        return {"error": f"No Bible reference detected in: {req.reference!r}"}
    verse_text = ""
    source_url = ""
    if req.include_text and ref.verse_start is not None:
        wol = _get_wol()
        url, html = await wol.get_bible_chapter(
            ref.book_num,
            ref.chapter,
            language=req.language,
            publication=req.publication,
        )
        v = get_verse(html, ref.book_num, ref.chapter, ref.verse_start, language=req.language)
        verse_text = v.text if v else ""
        source_url = url
    md = render_verse_block(
        ref,
        verse_text,
        template=req.template,  # type: ignore[arg-type]
        length=req.length,  # type: ignore[arg-type]
        language=req.language,
    )
    return {
        "markdown": md,
        "reference": ref.display(),
        "language": req.language,
        "source_url": source_url,
    }


@app.post("/api/v1/vault/index")
def post_vault_index(req: VaultIndexRequest) -> dict[str, Any]:
    """Sync an Obsidian vault into the local RAG store (incremental)."""
    from jw_mcp.server import _get_rag_store  # reuse the same store the MCP uses

    store = _get_rag_store()
    report = index_vault_to_rag(
        req.vault_root,
        store,
        state_path=req.state_path or None,
        glob=req.glob,
        require_tag=req.require_tag or None,
        min_chars=req.min_chars,
    )
    store.save()
    return report.to_dict()


@app.post("/api/v1/vault/export")
def post_vault_export(req: VaultExportRequest) -> dict[str, Any]:
    """Write one `.md` per JW Library backup note into the given vault."""
    report = export_backup_to_vault(
        req.backup_path,
        req.vault_dir,
        template=req.template,  # type: ignore[arg-type]
        length=req.length,  # type: ignore[arg-type]
        language=req.language,
        subdir=req.subdir,
        overwrite=req.overwrite,
    )
    return report.to_dict()


@app.on_event("shutdown")
async def shutdown() -> None:
    if _wol is not None:
        await _wol.aclose()
    if _cdn is not None:
        await _cdn.aclose()
