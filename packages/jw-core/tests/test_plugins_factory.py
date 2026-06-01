"""Tests for jw_core.plugins.factory."""

from __future__ import annotations

from importlib.metadata import EntryPoint

import pytest

from jw_core.plugins import clear_plugin_cache, get_plugins
from jw_core.plugins.errors import PluginError


def _patch_eps(
    monkeypatch: pytest.MonkeyPatch,
    mapping: dict[str, list[tuple[EntryPoint, str, str]]],
) -> list[int]:
    calls: list[int] = []

    def fake_eps(*, group: str | None = None, **_):
        calls.append(1)
        if group is None:
            return []
        return [ep for ep, _, _ in mapping.get(group, [])]

    def fake_dist(ep: EntryPoint) -> tuple[str, str]:
        for vals in mapping.values():
            for got, name, ver in vals:
                if got is ep:
                    return name, ver
        return "unknown", "0.0.0"

    monkeypatch.setattr("jw_core.plugins.registry.entry_points", fake_eps)
    monkeypatch.setattr("jw_core.plugins.registry._distribution_for_entry_point", fake_dist)
    return calls


def test_get_plugins_returns_dict(monkeypatch: pytest.MonkeyPatch) -> None:
    ep = EntryPoint(name="foo", value="some.mod:foo", group="jw_agent_toolkit.agents")
    _patch_eps(monkeypatch, {"jw_agent_toolkit.agents": [(ep, "pkg", "1.0")]})
    out = get_plugins("jw_agent_toolkit.agents")
    assert "foo" in out
    assert out["foo"].dist_name == "pkg"


def test_get_plugins_is_cached(monkeypatch: pytest.MonkeyPatch) -> None:
    ep = EntryPoint(name="foo", value="some.mod:foo", group="jw_agent_toolkit.agents")
    calls = _patch_eps(monkeypatch, {"jw_agent_toolkit.agents": [(ep, "pkg", "1.0")]})
    get_plugins("jw_agent_toolkit.agents")
    get_plugins("jw_agent_toolkit.agents")
    get_plugins("jw_agent_toolkit.agents")
    assert len(calls) == 1


def test_clear_plugin_cache_forces_rediscovery(monkeypatch: pytest.MonkeyPatch) -> None:
    ep = EntryPoint(name="foo", value="some.mod:foo", group="jw_agent_toolkit.agents")
    calls = _patch_eps(monkeypatch, {"jw_agent_toolkit.agents": [(ep, "pkg", "1.0")]})
    get_plugins("jw_agent_toolkit.agents")
    clear_plugin_cache()
    get_plugins("jw_agent_toolkit.agents")
    assert len(calls) == 2


def test_get_plugins_rejects_unknown_group(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_eps(monkeypatch, {})
    with pytest.raises(PluginError):
        get_plugins("jw_agent_toolkit.totally_made_up")


def test_get_plugins_empty_when_no_entries(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_eps(monkeypatch, {})
    assert get_plugins("jw_agent_toolkit.agents") == {}


def test_get_plugins_returns_copy(monkeypatch: pytest.MonkeyPatch) -> None:
    ep = EntryPoint(name="foo", value="some.mod:foo", group="jw_agent_toolkit.agents")
    _patch_eps(monkeypatch, {"jw_agent_toolkit.agents": [(ep, "pkg", "1.0")]})
    out_a = get_plugins("jw_agent_toolkit.agents")
    out_a["INJECTED"] = out_a["foo"]
    out_b = get_plugins("jw_agent_toolkit.agents")
    assert "INJECTED" not in out_b
