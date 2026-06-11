"""F72 drift.analyze exposure via F65 meta-orchestrator."""

from __future__ import annotations

import json
from pathlib import Path

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


def test_drift_analyze_in_builtin_tools() -> None:
    assert "drift.analyze" in BUILTIN_TOOL_NAMES


@pytest.mark.asyncio
async def test_drift_analyze_tool_runs(tmp_path: Path) -> None:
    path = tmp_path / "chunks.jsonl"
    lines = [
        {"text": "old1", "year": 1985, "embedding": [1.0, 0.0]},
        {"text": "old2", "year": 1986, "embedding": [0.99, 0.01]},
        {"text": "old3", "year": 1987, "embedding": [1.0, 0.05]},
        {"text": "new1", "year": 2024, "embedding": [0.0, 1.0]},
        {"text": "new2", "year": 2025, "embedding": [0.05, 0.99]},
        {"text": "new3", "year": 2026, "embedding": [0.0, 1.0]},
    ]
    path.write_text("\n".join(json.dumps(d) for d in lines))

    register_builtin_tools()
    tool = get_tool("drift.analyze")
    out = await tool.callable_(
        query="x", chunks_path=str(path), language="es"
    )
    assert out["agent_name"] == "drift_analyze"
    assert out["report"]["drift_events"]
