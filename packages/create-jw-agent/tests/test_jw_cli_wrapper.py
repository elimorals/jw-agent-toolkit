"""Tests for the `jw create-agent` wrapper in jw-cli."""

from __future__ import annotations

import shutil
import subprocess
import sys

import pytest
from typer.testing import CliRunner


runner = CliRunner()


def test_jw_cli_create_agent_help_lists_command() -> None:
    """`jw --help` should mention create-agent."""

    from jw_cli.main import app

    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "create-agent" in result.stdout


def test_wrapper_calls_standalone_binary(monkeypatch: pytest.MonkeyPatch) -> None:
    """The wrapper invokes the standalone binary with the same args."""

    from jw_cli.commands import create_agent as mod

    captured: dict = {}

    def fake_which(binary: str) -> str:
        captured["which"] = binary
        return f"/fake/path/{binary}"

    def fake_run(cmd: list[str], check: bool = False):
        captured["cmd"] = cmd

        class _R:
            returncode = 0

        return _R()

    monkeypatch.setattr(mod.shutil, "which", fake_which)
    monkeypatch.setattr(mod.subprocess, "run", fake_run)
    monkeypatch.setattr(mod.sys, "argv", ["jw", "create-agent", "my-plugin", "--type=agent"])

    import typer

    with pytest.raises(typer.Exit) as exc_info:
        mod.create_agent_cmd()
    assert exc_info.value.exit_code == 0
    assert captured["which"] == "create-jw-agent"
    assert "my-plugin" in captured["cmd"]
    assert "--type=agent" in captured["cmd"]


def test_wrapper_emits_install_hint_when_missing(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str],
) -> None:
    """When create-jw-agent is not on PATH, the wrapper tells the user how to install it."""

    from jw_cli.commands import create_agent as mod

    monkeypatch.setattr(mod.shutil, "which", lambda _: None)

    import typer

    with pytest.raises(typer.Exit) as exc_info:
        mod.create_agent_cmd()
    assert exc_info.value.exit_code == 1
    err = capsys.readouterr().err
    assert "create-jw-agent" in err
    assert "uvx" in err or "pipx" in err
