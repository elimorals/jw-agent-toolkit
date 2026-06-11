"""F65 meta-orchestrator now exposes `broadcasting.visual_search`."""

from __future__ import annotations

from pathlib import Path

import pytest

from jw_agents.meta.builtin_tools import (
    BUILTIN_TOOL_NAMES,
    register_builtin_tools,
)
from jw_agents.meta.registry import clear_registry, get_tool


@pytest.fixture(autouse=True)
def _setup(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("JW_VISUAL_INDEX_ROOT", str(tmp_path / "visual"))
    clear_registry()
    yield
    clear_registry()


def test_broadcasting_visual_search_in_builtin_tools() -> None:
    assert "broadcasting.visual_search" in BUILTIN_TOOL_NAMES


@pytest.mark.asyncio
async def test_broadcasting_visual_search_tool_runs_on_empty_index() -> None:
    register_builtin_tools()
    tool = get_tool("broadcasting.visual_search")
    out = await tool.callable_(query="anything", top_k=3)
    assert isinstance(out, dict)
    assert out["agent_name"] == "broadcasting_visual_search"
    assert "findings" in out
