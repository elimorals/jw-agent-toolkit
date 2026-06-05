"""Tests for jw_core.plugins.policy."""

from __future__ import annotations

import pytest
from jw_core.plugins.contracts import EntryPointSpec
from jw_core.plugins.errors import PluginConflictError
from jw_core.plugins.policy import (
    ConflictPolicy,
    apply_conflict_policy,
    read_env_set,
    read_policy_from_env,
)


def _spec(name: str, dist: str) -> EntryPointSpec:
    return EntryPointSpec(
        name=name,
        group="jw_agent_toolkit.agents",
        module=f"{dist}.mod",
        attr=name,
        dist_name=dist,
        dist_version="1.0.0",
    )


def test_conflict_policy_enum_values() -> None:
    assert ConflictPolicy.FIRST_WINS.value == "first_wins"
    assert ConflictPolicy.LAST_WINS.value == "last_wins"
    assert ConflictPolicy.NAMESPACED.value == "namespaced"
    assert ConflictPolicy.REJECT.value == "reject"


def test_read_env_set_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("JW_PLUGINS_ALLOW_LIST", raising=False)
    assert read_env_set("JW_PLUGINS_ALLOW_LIST") is None


def test_read_env_set_empty_treated_as_none(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JW_PLUGINS_ALLOW_LIST", "")
    assert read_env_set("JW_PLUGINS_ALLOW_LIST") is None


def test_read_env_set_parses_csv(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JW_PLUGINS_ALLOW_LIST", "a, b ,c")
    assert read_env_set("JW_PLUGINS_ALLOW_LIST") == {"a", "b", "c"}


def test_read_policy_from_env_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("JW_PLUGINS_CONFLICT_POLICY", raising=False)
    assert read_policy_from_env() == ConflictPolicy.NAMESPACED


def test_read_policy_from_env_explicit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JW_PLUGINS_CONFLICT_POLICY", "first_wins")
    assert read_policy_from_env() == ConflictPolicy.FIRST_WINS


def test_read_policy_from_env_invalid_falls_back(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    monkeypatch.setenv("JW_PLUGINS_CONFLICT_POLICY", "weird")
    with caplog.at_level("WARNING"):
        assert read_policy_from_env() == ConflictPolicy.NAMESPACED
    assert any("weird" in r.message for r in caplog.records)


def test_apply_first_wins_keeps_existing() -> None:
    current = {"x": _spec("x", "pkg-a")}
    new = _spec("x", "pkg-b")
    out = apply_conflict_policy(current, new, ConflictPolicy.FIRST_WINS)
    assert out["x"].dist_name == "pkg-a"


def test_apply_last_wins_replaces() -> None:
    current = {"x": _spec("x", "pkg-a")}
    new = _spec("x", "pkg-b")
    out = apply_conflict_policy(current, new, ConflictPolicy.LAST_WINS)
    assert out["x"].dist_name == "pkg-b"


def test_apply_namespaced_emits_both_under_qualified_names() -> None:
    current = {"x": _spec("x", "pkg-a")}
    new = _spec("x", "pkg-b")
    out = apply_conflict_policy(current, new, ConflictPolicy.NAMESPACED)
    assert "x" not in out
    assert out["pkg-a:x"].dist_name == "pkg-a"
    assert out["pkg-b:x"].dist_name == "pkg-b"


def test_apply_namespaced_no_conflict_keeps_bare_name() -> None:
    current: dict = {}
    new = _spec("x", "pkg-a")
    out = apply_conflict_policy(current, new, ConflictPolicy.NAMESPACED)
    assert "x" in out
    assert "pkg-a:x" not in out


def test_apply_reject_raises() -> None:
    current = {"x": _spec("x", "pkg-a")}
    new = _spec("x", "pkg-b")
    with pytest.raises(PluginConflictError) as exc_info:
        apply_conflict_policy(current, new, ConflictPolicy.REJECT)
    assert "pkg-a" in str(exc_info.value)
    assert "pkg-b" in str(exc_info.value)


def test_apply_logs_warning_on_conflict(caplog: pytest.LogCaptureFixture) -> None:
    current = {"x": _spec("x", "pkg-a")}
    new = _spec("x", "pkg-b")
    with caplog.at_level("WARNING"):
        apply_conflict_policy(current, new, ConflictPolicy.FIRST_WINS)
    assert any("conflict" in r.message.lower() for r in caplog.records)
