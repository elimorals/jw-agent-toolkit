"""F71 book_camera.analyze exposure via F65 meta-orchestrator."""

from __future__ import annotations

import pytest

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


def test_book_camera_analyze_in_builtin_tools() -> None:
    assert "book_camera.analyze" in BUILTIN_TOOL_NAMES


@pytest.mark.asyncio
async def test_book_camera_analyze_tool_runs_with_text() -> None:
    register_builtin_tools()
    tool = get_tool("book_camera.analyze")
    out = await tool.callable_(ocr_text="Juan 3:16", language="es")
    assert isinstance(out, dict)
    assert out["agent_name"] == "book_camera_analyze"
    assert out["result"]["detected"]["kind"] == "bible_verse"
