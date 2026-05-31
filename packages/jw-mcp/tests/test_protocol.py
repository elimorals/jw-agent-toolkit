"""MCP protocol tests via an in-process FastMCP Client.

These exercise the full MCP wire protocol (handshake → list_tools →
call_tool → response) — what an actual MCP host (Claude Desktop, Claude
Code, etc.) would see when it connects to `jw-mcp`. Running in-process
(no subprocess, no stdio) keeps them fast and deterministic.

What this proves:

  1. The server registers exactly the tools we expect (29 in v1.0, 47 after Modules 1-3).
  2. Every tool has a non-empty description (LLM consumes them).
  3. Every tool exposes an input schema (parameter discovery works).
  4. A pure tool (`resolve_reference`) round-trips: parameter → JSON
     response with correct shape.
  5. An async tool short-circuits its validation path before any network
     call (`get_chapter` with `book_num=0`).
  6. Error responses propagate via the `data["error"]` field, not raised.

These tests do NOT hit the network — only pure-CPU tools are invoked.
"""

from __future__ import annotations

import pytest
from fastmcp import Client
from jw_mcp.server import mcp

# ── Tool discovery (list_tools) ────────────────────────────────────────


_EXPECTED_TOOLS = {
    # Phase 1
    "resolve_reference",
    "get_chapter",
    "get_daily_text",
    "search_content",
    "get_article",
    # Phase 2
    "list_languages",
    "list_publication_files",
    "download_publication",
    # Phase 3
    "get_verse",
    "get_study_notes",
    "get_cross_references",
    "compare_translations",
    # Phase 4
    "search_topic_index",
    "get_topic_articles",
    # Phase 5 + 5.5
    "extract_epub_text",
    "inspect_jwpub_metadata",
    "extract_jwpub_text",
    "ingest_epub",
    "ingest_jwpub",
    # Phase 6
    "semantic_search",
    "ingest_bible_chapter",
    "ingest_search_topk",
    # Phase 7
    "research_topic",
    "verse_explainer",
    "meeting_helper",
    "apologetics",
    # Phase 9 / 10
    "get_cache_stats",
    "get_publication_toc",
    "list_weblang_languages",
    # Module 1 — workbook + WT study
    "workbook_helper",
    "public_talk_outline",
    # Module 2 — ministry
    "conversation_assistant",
    "list_known_objections",
    "presentation_builder",
    "list_audiences",
    "reverse_citation_lookup",
    "revisit_upsert",
    "revisit_list",
    "revisit_plan",
    "revisit_due",
    "revisit_delete",
    # Module 3 — audio
    "list_tts_engines",
    "read_verse_aloud",
    "read_article_aloud",
    "search_broadcasting",
    "index_broadcasting_vtt",
    # Phase 19 — JW Library integrations
    "open_in_jw_library",
    "import_jw_library_backup",
    "list_user_notes",
    "ingest_user_notes",
    "inspect_local_jw_library_tool",
    "sync_jw_library_backup",
    "register_jwpub_in_catalog",
    "find_publication_in_catalog",
    "open_publication_by_symbol",
    "check_jw_library_full_disk_access",
    "read_jw_library_live_userdata",
    # Phase 20 — Obsidian bridge
    "linkify_markdown_text",
    "convert_jw_links_in_markdown",
    "get_verse_as_markdown",
    "index_obsidian_vault",
    "export_jw_library_backup_to_vault",
    # Phase 23 — Citation integrity validator
    "validate_citations",
    # Phase 24 — Study conductor + student progress
    "prepare_lesson",
    "log_student_progress",
    "list_student_lessons",
    "set_student_goal",
    # Phase 25 — News monitor
    "news_digest",
    # Phase 26 — Student parts (Vida y Ministerio)
    "student_part_help",
    # Phase 27 — Pioneer monthly report
    "field_log_hours",
    "field_log_study",
    "field_monthly_report",
}


@pytest.mark.asyncio
async def test_mcp_lists_all_expected_tools() -> None:
    async with Client(mcp) as client:
        tools = await client.list_tools()
    names = {t.name for t in tools}
    missing = _EXPECTED_TOOLS - names
    extra = names - _EXPECTED_TOOLS
    assert not missing, f"Tools missing from server: {missing}"
    assert not extra, f"Tools present but not in EXPECTED set: {extra}"
    assert len(tools) == len(_EXPECTED_TOOLS)


@pytest.mark.asyncio
async def test_mcp_every_tool_has_description() -> None:
    """LLM clients need a description to pick the right tool."""
    async with Client(mcp) as client:
        tools = await client.list_tools()
    no_description = [t.name for t in tools if not t.description]
    assert not no_description, f"Tools missing description: {no_description}"


@pytest.mark.asyncio
async def test_mcp_every_tool_has_input_schema() -> None:
    """Parameter discovery is part of the MCP contract."""
    async with Client(mcp) as client:
        tools = await client.list_tools()
    for t in tools:
        assert t.inputSchema, f"Tool {t.name} has no input schema"
        # JSON Schema must declare an object type with properties.
        assert t.inputSchema.get("type") == "object"


# ── Tool invocation round-trip ────────────────────────────────────────


@pytest.mark.asyncio
async def test_mcp_call_resolve_reference_returns_canonical_structure() -> None:
    async with Client(mcp) as client:
        result = await client.call_tool(
            "resolve_reference",
            {"text": "Juan 3:16", "language": "es"},
        )
    payload = result.data
    assert payload["book_num"] == 43
    assert payload["chapter"] == 3
    assert payload["verse_start"] == 16
    assert payload["detected_language"] == "es"
    assert "wol.jw.org/es/wol/b/r4/lp-s/nwt/43/3" in payload["wol_url"]


@pytest.mark.asyncio
async def test_mcp_call_resolve_reference_returns_error_field_on_bad_input() -> None:
    """Failure surfaces via `data['error']`, not via an exception."""
    async with Client(mcp) as client:
        result = await client.call_tool(
            "resolve_reference",
            {"text": "gibberish-not-a-reference"},
        )
    assert "error" in result.data, f"Expected error field; got: {result.data}"


@pytest.mark.asyncio
async def test_mcp_call_get_chapter_validates_before_network() -> None:
    """`get_chapter(0, 1)` must short-circuit on validation, not crash."""
    async with Client(mcp) as client:
        result = await client.call_tool(
            "get_chapter",
            {"book_num": 0, "chapter": 1, "language": "en"},
        )
    assert "error" in result.data
    assert "1..66" in result.data["error"]


@pytest.mark.asyncio
async def test_mcp_call_get_cache_stats_returns_stats_shape() -> None:
    async with Client(mcp) as client:
        result = await client.call_tool("get_cache_stats", {})
    # Either enabled=False (no cache file) or has total/live/expired keys.
    assert "enabled" in result.data
    if result.data["enabled"]:
        for k in ("total", "live", "expired"):
            assert k in result.data


# ── Tool schema specifics ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_mcp_resolve_reference_schema_declares_text_required() -> None:
    async with Client(mcp) as client:
        tools = await client.list_tools()
    resolve = next(t for t in tools if t.name == "resolve_reference")
    schema = resolve.inputSchema
    assert "text" in schema.get("properties", {})
    assert "text" in schema.get("required", [])


@pytest.mark.asyncio
async def test_mcp_get_chapter_schema_includes_with_footnotes() -> None:
    """Phase 10 added `with_footnotes` — verify it's exposed in the schema."""
    async with Client(mcp) as client:
        tools = await client.list_tools()
    get_chapter = next(t for t in tools if t.name == "get_chapter")
    props = get_chapter.inputSchema.get("properties", {})
    assert "with_footnotes" in props


@pytest.mark.asyncio
async def test_mcp_get_daily_text_schema_includes_date() -> None:
    """Phase 10 added `date` — verify it's exposed."""
    async with Client(mcp) as client:
        tools = await client.list_tools()
    daily = next(t for t in tools if t.name == "get_daily_text")
    props = daily.inputSchema.get("properties", {})
    assert "date" in props


# ── Content shape (raw MCP wire format) ───────────────────────────────


@pytest.mark.asyncio
async def test_mcp_call_returns_text_content_in_wire_format() -> None:
    """The `content` field is what an MCP host actually receives on the wire."""
    async with Client(mcp) as client:
        result = await client.call_tool(
            "resolve_reference",
            {"text": "John 3:16"},
        )
    # `content` is a list of TextContent entries with raw JSON.
    assert result.content
    first = result.content[0]
    assert first.type == "text"
    # The text payload should parse as JSON and match the structured data.
    import json

    parsed = json.loads(first.text)
    assert parsed == result.data
