from __future__ import annotations

import asyncio
from pathlib import Path


def test_extract_structured_page_tool_registered() -> None:
    from jw_mcp.server import mcp

    tools = asyncio.run(mcp.list_tools())
    tool_names = {t.name for t in tools}
    assert "extract_structured_page" in tool_names
    assert "ingest_image_to_rag" in tool_names


def test_extract_structured_page_returns_dict(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("JW_VLM_PROVIDER", "fake")
    img = tmp_path / "p.png"
    img.write_bytes(b"\x89PNG")

    from jw_mcp.server import extract_structured_page as tool

    result = tool(image_path=str(img), language="en")
    assert isinstance(result, dict)
    assert "blocks" in result
    assert result["provider_name"] == "fake"
