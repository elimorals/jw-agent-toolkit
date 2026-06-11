"""F67 reason.doctrinal tool exposure via F65 meta-orchestrator."""

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


def test_reason_doctrinal_in_builtin_tools_list() -> None:
    assert "reason.doctrinal" in BUILTIN_TOOL_NAMES


@pytest.mark.asyncio
async def test_reason_doctrinal_tool_returns_tree_dict() -> None:
    register_builtin_tools()
    tool = get_tool("reason.doctrinal")
    out = await tool.callable_(
        question="¿qué enseña Juan 3:16?",
        language="es",
        max_steps=4,
        nli_mode="off",
    )
    assert isinstance(out, dict)
    assert "steps" in out
    assert out["question_original"] == "¿qué enseña Juan 3:16?"
