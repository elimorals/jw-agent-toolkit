"""Tests for jw-mcp ↔ jw_core.plugins tool registration."""

from __future__ import annotations

from typing import Any

import pytest

from jw_core.plugins import clear_plugin_cache
from jw_core.plugins.contracts import EntryPointSpec
from jw_mcp.server import register_plugin_tools


async def _fake_agent(**kwargs: Any) -> Any:
    return {"echo": kwargs}


class _FakeMCP:
    def __init__(self) -> None:
        self.registered: list[tuple[str, str]] = []

    def tool(self, name: str | None = None):
        def deco(fn):
            self.registered.append((name or fn.__name__, fn.__doc__ or ""))
            return fn

        return deco


@pytest.fixture(autouse=True)
def _reset_cache() -> None:
    clear_plugin_cache()
    yield
    clear_plugin_cache()


def test_register_plugin_tools_emits_one_tool_per_plugin(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    spec = EntryPointSpec(
        name="myagent",
        group="jw_agent_toolkit.agents",
        module="dummy",
        attr="myagent",
        dist_name="x",
        dist_version="1",
    )

    def fake_resolve(self: EntryPointSpec) -> Any:  # noqa: ARG001
        return _fake_agent

    monkeypatch.setattr(EntryPointSpec, "resolve", fake_resolve, raising=True)
    monkeypatch.setattr(
        "jw_mcp.server.get_plugins",
        lambda group: {"myagent": spec} if group == "jw_agent_toolkit.agents" else {},
    )

    mcp = _FakeMCP()
    register_plugin_tools(mcp)
    names = [n for n, _ in mcp.registered]
    assert "agent.myagent" in names


def test_register_plugin_tools_handles_broken_plugin(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    spec = EntryPointSpec(
        name="bad",
        group="jw_agent_toolkit.agents",
        module="dummy",
        attr="bad",
        dist_name="x",
        dist_version="1",
    )

    def fake_resolve(self: EntryPointSpec) -> Any:  # noqa: ARG001
        raise RuntimeError("boom")

    monkeypatch.setattr(EntryPointSpec, "resolve", fake_resolve, raising=True)
    monkeypatch.setattr(
        "jw_mcp.server.get_plugins",
        lambda group: {"bad": spec} if group == "jw_agent_toolkit.agents" else {},
    )

    mcp = _FakeMCP()
    register_plugin_tools(mcp)
    assert mcp.registered == []
