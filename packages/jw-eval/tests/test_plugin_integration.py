"""Tests for jw-eval ↔ jw_core.plugins integration."""

from __future__ import annotations

from typing import Any

import pytest

from jw_core.plugins import clear_plugin_cache
from jw_core.plugins.contracts import EntryPointSpec
from jw_eval.cli import default_agent_registry


async def _fake_plugin_agent(**kwargs: Any) -> Any:
    return {"findings": [], "echo": kwargs, "agent": "fake_plugin"}


@pytest.fixture(autouse=True)
def _reset_cache() -> None:
    clear_plugin_cache()
    yield
    clear_plugin_cache()


def test_default_registry_includes_hardcoded_agents() -> None:
    reg = default_agent_registry()
    assert "apologetics" in reg
    assert "verse_explainer" in reg


def test_default_registry_merges_plugin_agents(monkeypatch: pytest.MonkeyPatch) -> None:
    spec = EntryPointSpec(
        name="fake_plugin",
        group="jw_agent_toolkit.agents",
        module="dummy",
        attr="fake_plugin",
        dist_name="fake-pkg",
        dist_version="0.1.0",
    )

    def fake_resolve(self: EntryPointSpec) -> Any:  # noqa: ARG001
        return _fake_plugin_agent

    monkeypatch.setattr(EntryPointSpec, "resolve", fake_resolve, raising=True)
    monkeypatch.setattr(
        "jw_eval.cli.get_plugins",
        lambda group: {"fake_plugin": spec} if group == "jw_agent_toolkit.agents" else {},
    )
    reg = default_agent_registry()
    assert "fake_plugin" in reg


def test_plugin_does_not_override_core_agent(monkeypatch: pytest.MonkeyPatch) -> None:
    spec = EntryPointSpec(
        name="apologetics",
        group="jw_agent_toolkit.agents",
        module="dummy",
        attr="apologetics",
        dist_name="bad-pkg",
        dist_version="0.1.0",
    )

    def fake_resolve(self: EntryPointSpec) -> Any:  # noqa: ARG001
        return _fake_plugin_agent

    monkeypatch.setattr(EntryPointSpec, "resolve", fake_resolve, raising=True)
    monkeypatch.setattr(
        "jw_eval.cli.get_plugins",
        lambda group: {"apologetics": spec} if group == "jw_agent_toolkit.agents" else {},
    )
    reg = default_agent_registry()
    assert reg["apologetics"] is not _fake_plugin_agent
