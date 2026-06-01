"""Tests for `jw plugins {list,verify,disable}`."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from jw_cli.main import app
from jw_core.plugins import clear_plugin_cache
from jw_core.plugins.contracts import EntryPointSpec, VerifyReport


runner = CliRunner()


@pytest.fixture(autouse=True)
def _reset_cache() -> None:
    clear_plugin_cache()
    yield
    clear_plugin_cache()


def _spec(name: str = "demo") -> EntryPointSpec:
    return EntryPointSpec(
        name=name,
        group="jw_agent_toolkit.agents",
        module="m",
        attr=name,
        dist_name="demo-pkg",
        dist_version="1.0.0",
    )


def test_plugins_list_default_human(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "jw_cli.commands.plugins.get_plugins",
        lambda group: {"demo": _spec()} if group == "jw_agent_toolkit.agents" else {},
    )
    result = runner.invoke(app, ["plugins", "list"])
    assert result.exit_code == 0
    assert "demo" in result.stdout
    assert "demo-pkg" in result.stdout


def test_plugins_list_json(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "jw_cli.commands.plugins.get_plugins",
        lambda group: {"demo": _spec()} if group == "jw_agent_toolkit.agents" else {},
    )
    result = runner.invoke(app, ["plugins", "list", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert "jw_agent_toolkit.agents" in data
    assert data["jw_agent_toolkit.agents"][0]["name"] == "demo"


def test_plugins_verify_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    rep = VerifyReport(
        name="demo",
        group="jw_agent_toolkit.agents",
        dist_name="demo-pkg",
        dist_version="1.0.0",
        ok=True,
        required_present=("__call__",),
        required_missing=(),
        optional_present=("languages",),
        optional_missing=("version",),
        version_constraint=None,
        version_satisfied=True,
        errors=(),
    )

    def fake_verify(name: str, group: str) -> Any:  # noqa: ARG001
        return rep

    monkeypatch.setattr("jw_cli.commands.plugins.verify_plugin", fake_verify)
    result = runner.invoke(app, ["plugins", "verify", "demo"])
    assert result.exit_code == 0
    assert "ok" in result.stdout.lower()


def test_plugins_verify_fail(monkeypatch: pytest.MonkeyPatch) -> None:
    rep = VerifyReport(
        name="bad",
        group="jw_agent_toolkit.agents",
        dist_name="bad-pkg",
        dist_version="1.0.0",
        ok=False,
        required_present=(),
        required_missing=("__call__",),
        optional_present=(),
        optional_missing=("languages",),
        version_constraint=None,
        version_satisfied=True,
        errors=(),
    )
    monkeypatch.setattr(
        "jw_cli.commands.plugins.verify_plugin", lambda n, g: rep  # noqa: ARG005
    )
    result = runner.invoke(app, ["plugins", "verify", "bad"])
    assert result.exit_code == 2


def test_plugins_disable_writes_config(tmp_path: Path) -> None:
    cfg = tmp_path / "plugins.toml"
    result = runner.invoke(
        app, ["plugins", "disable", "spammy", "--config", str(cfg)]
    )
    assert result.exit_code == 0
    assert cfg.exists()
    text = cfg.read_text()
    assert "spammy" in text
    assert "[deny]" in text or "deny" in text


def test_plugins_disable_appends(tmp_path: Path) -> None:
    cfg = tmp_path / "plugins.toml"
    runner.invoke(app, ["plugins", "disable", "a", "--config", str(cfg)])
    runner.invoke(app, ["plugins", "disable", "b", "--config", str(cfg)])
    text = cfg.read_text()
    assert "a" in text and "b" in text
