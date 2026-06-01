"""Tests for jw_core.plugins.registry — discovery with monkey-patched entry points."""

from __future__ import annotations

from importlib.metadata import EntryPoint
from typing import Any

import pytest

from jw_core.plugins.registry import _discover, _entry_points_for_group


def _ep(name: str, group: str, value: str | None = None) -> EntryPoint:
    return EntryPoint(
        name=name,
        value=value or "tests.fakes.agent_module:my_agent",
        group=group,
    )


def _patch_entry_points(
    monkeypatch: pytest.MonkeyPatch,
    mapping: dict[str, list[tuple[EntryPoint, str, str]]],
) -> None:
    def fake_eps(*, group: str | None = None, **_: Any):
        if group is None:
            flat: list[EntryPoint] = []
            for vals in mapping.values():
                flat.extend(ep for ep, _, _ in vals)
            return flat
        return [ep for ep, _, _ in mapping.get(group, [])]

    def fake_dist_for_ep(ep: EntryPoint) -> tuple[str, str]:
        for vals in mapping.values():
            for got_ep, name, ver in vals:
                if got_ep is ep:
                    return name, ver
        return "unknown", "0.0.0"

    monkeypatch.setattr("jw_core.plugins.registry.entry_points", fake_eps)
    monkeypatch.setattr(
        "jw_core.plugins.registry._distribution_for_entry_point", fake_dist_for_ep
    )


def test_entry_points_for_group_returns_list(monkeypatch: pytest.MonkeyPatch) -> None:
    ep = _ep("foo", "jw_agent_toolkit.agents")
    _patch_entry_points(monkeypatch, {"jw_agent_toolkit.agents": [(ep, "pkg-a", "1.0")]})
    got = _entry_points_for_group("jw_agent_toolkit.agents")
    assert [e.name for e in got] == ["foo"]


def test_discover_returns_dict_keyed_by_name(monkeypatch: pytest.MonkeyPatch) -> None:
    ep = _ep("translation_helper", "jw_agent_toolkit.agents")
    _patch_entry_points(
        monkeypatch,
        {"jw_agent_toolkit.agents": [(ep, "trans-pkg", "1.2.3")]},
    )
    out = _discover("jw_agent_toolkit.agents")
    assert "translation_helper" in out
    spec = out["translation_helper"]
    assert spec.dist_name == "trans-pkg"
    assert spec.dist_version == "1.2.3"


def test_discover_filtered_by_allow_list(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JW_PLUGINS_ALLOW_LIST", "wanted")
    eps = [
        _ep("wanted", "jw_agent_toolkit.agents"),
        _ep("not_wanted", "jw_agent_toolkit.agents"),
    ]
    _patch_entry_points(
        monkeypatch,
        {"jw_agent_toolkit.agents": [(eps[0], "pkg-a", "1"), (eps[1], "pkg-b", "1")]},
    )
    out = _discover("jw_agent_toolkit.agents")
    assert set(out.keys()) == {"wanted"}


def test_discover_filtered_by_deny_list(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JW_PLUGINS_DENY_LIST", "banned")
    eps = [
        _ep("ok", "jw_agent_toolkit.agents"),
        _ep("banned", "jw_agent_toolkit.agents"),
    ]
    _patch_entry_points(
        monkeypatch,
        {"jw_agent_toolkit.agents": [(eps[0], "pkg-a", "1"), (eps[1], "pkg-b", "1")]},
    )
    out = _discover("jw_agent_toolkit.agents")
    assert set(out.keys()) == {"ok"}


def test_discover_conflict_namespaced_default(monkeypatch: pytest.MonkeyPatch) -> None:
    eps = [
        _ep("dup", "jw_agent_toolkit.agents"),
        _ep("dup", "jw_agent_toolkit.agents"),
    ]
    _patch_entry_points(
        monkeypatch,
        {"jw_agent_toolkit.agents": [(eps[0], "pkg-a", "1"), (eps[1], "pkg-b", "1")]},
    )
    out = _discover("jw_agent_toolkit.agents")
    assert "dup" not in out
    assert "pkg-a:dup" in out
    assert "pkg-b:dup" in out


def test_discover_first_wins_via_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JW_PLUGINS_CONFLICT_POLICY", "first_wins")
    eps = [
        _ep("dup", "jw_agent_toolkit.agents"),
        _ep("dup", "jw_agent_toolkit.agents"),
    ]
    _patch_entry_points(
        monkeypatch,
        {"jw_agent_toolkit.agents": [(eps[0], "pkg-a", "1"), (eps[1], "pkg-b", "1")]},
    )
    out = _discover("jw_agent_toolkit.agents")
    assert "dup" in out
    assert out["dup"].dist_name == "pkg-a"


def test_discover_disabled_short_circuits(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JW_PLUGINS_DISABLED", "1")
    eps = [_ep("foo", "jw_agent_toolkit.agents")]
    _patch_entry_points(monkeypatch, {"jw_agent_toolkit.agents": [(eps[0], "pkg-a", "1")]})
    assert _discover("jw_agent_toolkit.agents") == {}


def test_discover_unknown_group_returns_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_entry_points(monkeypatch, {})
    assert _discover("jw_agent_toolkit.bogus") == {}
