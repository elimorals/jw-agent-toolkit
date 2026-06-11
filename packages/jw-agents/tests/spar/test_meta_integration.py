"""F65 meta-orchestrator now exposes `spar.session` as a builtin tool."""

from __future__ import annotations

import pytest

from jw_agents.meta.builtin_tools import (
    BUILTIN_TOOL_NAMES,
    register_builtin_tools,
)
from jw_agents.meta.registry import clear_registry, get_tool
from jw_agents.spar.session import clear_sessions


@pytest.fixture(autouse=True)
def _clean() -> None:
    clear_registry()
    clear_sessions()
    yield
    clear_registry()
    clear_sessions()


def test_spar_session_is_in_builtin_tools_list() -> None:
    assert "spar.session" in BUILTIN_TOOL_NAMES


@pytest.mark.asyncio
async def test_spar_session_tool_runs_complete_session() -> None:
    register_builtin_tools()
    tool = get_tool("spar.session")
    out = await tool.callable_(
        persona="atheist",
        language="es",
        user_turns=["Hola, ¿podemos hablar?", "Como dice Juan 3:16..."],
    )
    assert isinstance(out, dict)
    assert out["closed"] is True
    assert out["persona"]["key"] == "atheist"
    assert len(out["user_turns"]) == 2
    assert out["score_summary"] is not None
    assert out["score_summary"]["turns"] == 2.0
