"""Tests for BrainDomain plugin discovery."""

from __future__ import annotations

from typing import Any

import pytest
from jw_brain.domain.registry import discover_domains


@pytest.fixture(autouse=True)
def _clear_cache() -> None:
    from jw_core.plugins import clear_plugin_cache

    clear_plugin_cache()
    yield
    clear_plugin_cache()


def test_builtin_tj_always_present() -> None:
    domains = discover_domains()
    assert "tj" in domains
    tj = domains["tj"]
    assert tj.name == "tj"
    assert any(n.name == "Verse" for n in tj.nodes)


def test_plugin_domain_discovered_via_f41(monkeypatch: pytest.MonkeyPatch) -> None:
    from jw_core.plugins.contracts import EntryPointSpec

    class _FinDom:
        name = "finance"
        nodes = [type("N", (), {"name": "Transaction"})()]
        edges = [type("E", (), {"name": "PAID_TO"})()]

    spec = EntryPointSpec(
        name="finance",
        group="jw_agent_toolkit.brain_domains",
        module="dummy",
        attr="FinanceBrainDomain",
        dist_name="jw-brain-finance-plugin",
        dist_version="0.1.0",
    )

    def fake_resolve(self: EntryPointSpec) -> Any:  # noqa: ARG001
        return _FinDom

    monkeypatch.setattr(EntryPointSpec, "resolve", fake_resolve, raising=True)
    monkeypatch.setattr(
        "jw_brain.domain.registry.get_plugins",
        lambda group: {"finance": spec} if group == "jw_agent_toolkit.brain_domains" else {},
    )

    domains = discover_domains()
    assert "tj" in domains
    assert "finance" in domains
    assert domains["finance"].name == "finance"


def test_broken_plugin_does_not_crash_discovery(monkeypatch: pytest.MonkeyPatch) -> None:
    from jw_core.plugins.contracts import EntryPointSpec

    spec = EntryPointSpec(
        name="bad",
        group="jw_agent_toolkit.brain_domains",
        module="dummy",
        attr="X",
        dist_name="bad-pkg",
        dist_version="0.1.0",
    )

    def boom(self: EntryPointSpec) -> Any:  # noqa: ARG001
        raise RuntimeError("import failed")

    monkeypatch.setattr(EntryPointSpec, "resolve", boom, raising=True)
    monkeypatch.setattr(
        "jw_brain.domain.registry.get_plugins",
        lambda group: {"bad": spec} if group == "jw_agent_toolkit.brain_domains" else {},
    )

    domains = discover_domains()
    assert "bad" not in domains
    assert "tj" in domains


def test_plugin_cannot_override_builtin_tj(monkeypatch: pytest.MonkeyPatch) -> None:
    """A malicious plugin trying to shadow 'tj' must be ignored."""

    from jw_core.plugins.contracts import EntryPointSpec

    class _FakeTJ:
        name = "tj"
        nodes = []
        edges = []

    spec = EntryPointSpec(
        name="tj",
        group="jw_agent_toolkit.brain_domains",
        module="evil",
        attr="EvilTJ",
        dist_name="evil-pkg",
        dist_version="0.1.0",
    )
    monkeypatch.setattr(EntryPointSpec, "resolve", lambda self: _FakeTJ, raising=True)
    monkeypatch.setattr(
        "jw_brain.domain.registry.get_plugins",
        lambda group: {"tj": spec} if group == "jw_agent_toolkit.brain_domains" else {},
    )

    domains = discover_domains()
    assert domains["tj"].__class__.__name__ == "TJBrainDomain"  # builtin wins
