"""Tool registry for the meta-orchestrator."""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from jw_agents.meta.registry import (
    ToolNotFound,
    clear_registry,
    get_tool,
    list_tools,
    register_tool,
)


@pytest.fixture(autouse=True)
def _clean() -> Iterator[None]:
    clear_registry()
    yield
    clear_registry()


async def _fake_agent(arg1: str = "x") -> dict:
    return {"agent_name": "fake", "findings": [], "echo": arg1}


def test_register_and_list_tool() -> None:
    register_tool(
        name="fake.tool",
        callable_=_fake_agent,
        description="A fake tool.",
        args_schema={"arg1": "str"},
    )
    tools = list_tools()
    assert "fake.tool" in {t.name for t in tools}


def test_register_duplicate_overrides_with_warning() -> None:
    register_tool(name="x", callable_=_fake_agent, description="A", args_schema={})
    register_tool(name="x", callable_=_fake_agent, description="B", args_schema={})
    tools = {t.name: t for t in list_tools()}
    assert tools["x"].description == "B"


def test_get_tool_returns_callable() -> None:
    register_tool(
        name="fake.tool", callable_=_fake_agent, description="x", args_schema={}
    )
    tool = get_tool("fake.tool")
    assert callable(tool.callable_)


def test_get_tool_missing_raises() -> None:
    with pytest.raises(ToolNotFound):
        get_tool("does.not.exist")


def test_list_tools_empty_returns_empty_list() -> None:
    assert list_tools() == []
