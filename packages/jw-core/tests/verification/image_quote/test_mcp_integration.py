"""F70 MCP tool integration."""

from __future__ import annotations

import asyncio
from pathlib import Path

from PIL import Image


def _call(tool, **kwargs):
    fn = getattr(tool, "fn", tool)
    return asyncio.run(fn(**kwargs))


def test_mcp_verify_image_quote_tool_returns_verdict(tmp_path: Path) -> None:
    from jw_mcp.server import verify_image_quote_tool

    img = tmp_path / "x.jpg"
    Image.new("RGB", (32, 32), color=(120, 200, 80)).save(img, "JPEG")
    out = _call(
        verify_image_quote_tool,
        image_path=str(img),
        ocr_text_override="Que el amor de Jehová guíe nuestras decisiones.",
    )
    assert isinstance(out, dict)
    assert "verdict" in out
    assert out["verdict"] in (
        "SUPPORTED",
        "DISTORTED",
        "FABRICATED",
        "UNVERIFIABLE",
    )
    assert "extracted_quote" in out
