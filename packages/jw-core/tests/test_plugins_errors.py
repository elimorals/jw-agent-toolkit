"""Tests for jw_core.plugins.errors."""

from __future__ import annotations

import pytest

from jw_core.plugins.errors import (
    PluginConflictError,
    PluginContractError,
    PluginError,
    PluginVersionMismatch,
)


def test_plugin_error_is_base() -> None:
    assert issubclass(PluginConflictError, PluginError)
    assert issubclass(PluginContractError, PluginError)
    assert issubclass(PluginVersionMismatch, PluginError)


def test_plugin_conflict_error_carries_names() -> None:
    err = PluginConflictError(
        name="dup",
        group="jw_agent_toolkit.agents",
        dist_names=("pkg-a", "pkg-b"),
        policy="reject",
    )
    assert err.name == "dup"
    assert err.dist_names == ("pkg-a", "pkg-b")
    assert "dup" in str(err)
    assert "pkg-a" in str(err)
    assert "pkg-b" in str(err)


def test_plugin_version_mismatch_carries_constraint() -> None:
    err = PluginVersionMismatch(
        plugin_name="foo",
        constraint="jw-agent-toolkit>=99.0",
        installed_version="0.1.0",
    )
    assert err.constraint == "jw-agent-toolkit>=99.0"
    assert "99.0" in str(err)
    assert "0.1.0" in str(err)


def test_plugin_contract_error_carries_missing() -> None:
    err = PluginContractError(
        plugin_name="foo",
        group="jw_agent_toolkit.agents",
        missing=["__call__"],
        extra={"reason": "not callable"},
    )
    assert err.missing == ["__call__"]
    assert "__call__" in str(err)


def test_can_raise_and_catch() -> None:
    with pytest.raises(PluginError):
        raise PluginConflictError("a", "g", ("x", "y"), "reject")
