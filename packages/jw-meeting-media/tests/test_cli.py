"""F57 — CLI smoke tests."""

from __future__ import annotations

from typer.testing import CliRunner

from jw_meeting_media.cli import app


def test_help_lists_subcommands():
    runner = CliRunner()
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "discover" in result.stdout
    assert "download" in result.stdout
    assert "list" in result.stdout


def test_list_no_programs(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "jw_meeting_media.cli._default_cache_root", lambda: tmp_path
    )
    runner = CliRunner()
    result = runner.invoke(app, ["list"])
    assert result.exit_code == 0
    assert "No programs" in result.stdout
