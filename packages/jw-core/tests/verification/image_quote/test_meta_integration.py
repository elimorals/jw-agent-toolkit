"""F70 verification.image_quote exposure via F65 meta-orchestrator."""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from jw_agents.meta.builtin_tools import (
    BUILTIN_TOOL_NAMES,
    register_builtin_tools,
)
from jw_agents.meta.registry import clear_registry, get_tool


@pytest.fixture(autouse=True)
def _clean() -> None:
    clear_registry()
    yield
    clear_registry()


def test_verification_image_quote_in_builtin_tools() -> None:
    assert "verification.image_quote" in BUILTIN_TOOL_NAMES


@pytest.mark.asyncio
async def test_verification_image_quote_tool_runs(tmp_path: Path) -> None:
    img = tmp_path / "x.jpg"
    Image.new("RGB", (32, 32), color=(120, 200, 80)).save(img, "JPEG")
    register_builtin_tools()
    tool = get_tool("verification.image_quote")
    out = await tool.callable_(
        image_path=str(img),
        ocr_text_override="hi",
    )
    assert isinstance(out, dict)
    assert out["agent_name"] == "verify_image_quote"
    assert "findings" in out
    assert out["verdict"]["verdict"] == "UNVERIFIABLE"
