"""Smoke tests for the MCP server.

These don't hit the network — they only verify the tool functions can be
imported, the FastMCP instance is built, and the reference-resolution tool
works on a known input.
"""

from jw_mcp import server


def test_mcp_instance_exists() -> None:
    assert server.mcp.name == "jw-agent-toolkit"


def test_resolve_reference_known_input() -> None:
    out = server.resolve_reference("Juan 3:16", language="es")
    assert "error" not in out
    assert out["book_num"] == 43
    assert out["chapter"] == 3
    assert out["verse_start"] == 16
    assert out["detected_language"] == "es"
    assert "wol.jw.org/es/wol/b/r4/lp-s/nwt/43/3" in out["wol_url"]


def test_resolve_reference_no_match() -> None:
    out = server.resolve_reference("hello world")
    assert "error" in out


def test_get_chapter_validates_book_num() -> None:
    import asyncio

    out = asyncio.run(server.get_chapter(0, 1))
    assert "error" in out
