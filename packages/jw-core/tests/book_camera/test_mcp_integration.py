"""F71 MCP tool integration."""

from __future__ import annotations

import asyncio


def _call(tool, **kwargs):
    fn = getattr(tool, "fn", tool)
    return asyncio.run(fn(**kwargs))


def test_mcp_book_camera_analyze_with_ocr_text() -> None:
    from jw_mcp.server import book_camera_analyze

    out = _call(
        book_camera_analyze,
        image_path=None,
        ocr_text="Juan 3:16",
        language="es",
    )
    assert isinstance(out, dict)
    assert out["detected"]["kind"] == "bible_verse"
    assert out["suggested_actions"]
