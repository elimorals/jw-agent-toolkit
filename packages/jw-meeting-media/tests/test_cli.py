"""F57 — CLI smoke tests."""

from __future__ import annotations

from jw_meeting_media.cli import app
from typer.testing import CliRunner


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
    monkeypatch.setenv("JW_MEETING_HOME", str(tmp_path))
    runner = CliRunner()
    result = runner.invoke(app, ["list"])
    assert result.exit_code == 0
    assert "No programs" in result.stdout


# ── F57.16 congregation subcommand tests ────────────────────────────────


def test_help_lists_congregation_subcommand():
    runner = CliRunner()
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "congregation" in result.stdout


def test_cong_add_and_list(tmp_path, monkeypatch):
    monkeypatch.setenv("JW_MEETING_HOME", str(tmp_path))
    runner = CliRunner()
    r1 = runner.invoke(app, ["congregation", "add", "norte", "--language", "es"])
    assert r1.exit_code == 0, r1.stdout
    assert "norte" in r1.stdout
    r2 = runner.invoke(app, ["congregation", "list"])
    assert r2.exit_code == 0
    assert "norte" in r2.stdout
    assert "es" in r2.stdout


def test_cong_list_empty(tmp_path, monkeypatch):
    monkeypatch.setenv("JW_MEETING_HOME", str(tmp_path))
    runner = CliRunner()
    r = runner.invoke(app, ["congregation", "list"])
    assert r.exit_code == 0
    assert "No congregations" in r.stdout


def test_cong_remove(tmp_path, monkeypatch):
    monkeypatch.setenv("JW_MEETING_HOME", str(tmp_path))
    runner = CliRunner()
    runner.invoke(app, ["congregation", "add", "a", "--language", "es"])
    r = runner.invoke(app, ["congregation", "remove", "a"])
    assert r.exit_code == 0
    assert "Removed" in r.stdout
    r2 = runner.invoke(app, ["congregation", "list"])
    assert "a [es]" not in r2.stdout


def test_cong_remove_missing(tmp_path, monkeypatch):
    monkeypatch.setenv("JW_MEETING_HOME", str(tmp_path))
    runner = CliRunner()
    r = runner.invoke(app, ["congregation", "remove", "nope"])
    assert r.exit_code == 1


def test_cong_default_with_zero_returns_default(tmp_path, monkeypatch):
    monkeypatch.setenv("JW_MEETING_HOME", str(tmp_path))
    runner = CliRunner()
    r = runner.invoke(app, ["congregation", "default"])
    assert r.exit_code == 0
    assert "default" in r.stdout


def test_cong_default_with_single_resolves_to_it(tmp_path, monkeypatch):
    monkeypatch.setenv("JW_MEETING_HOME", str(tmp_path))
    runner = CliRunner()
    runner.invoke(app, ["congregation", "add", "only", "--language", "es"])
    r = runner.invoke(app, ["congregation", "default"])
    assert r.exit_code == 0
    assert "only" in r.stdout


def test_cong_default_with_multiple_errors(tmp_path, monkeypatch):
    monkeypatch.setenv("JW_MEETING_HOME", str(tmp_path))
    runner = CliRunner()
    runner.invoke(app, ["congregation", "add", "a", "--language", "es"])
    runner.invoke(app, ["congregation", "add", "b", "--language", "en"])
    r = runner.invoke(app, ["congregation", "default"])
    assert r.exit_code == 1
    assert "multiple congregations" in r.stderr


def test_list_with_no_programs_and_no_congregations(tmp_path, monkeypatch):
    """Backwards compat: sin registry, default congregation con cache vacío."""
    monkeypatch.setenv("JW_MEETING_HOME", str(tmp_path))
    runner = CliRunner()
    r = runner.invoke(app, ["list"])
    assert r.exit_code == 0
    assert "No programs" in r.stdout


def test_list_with_explicit_congregation(tmp_path, monkeypatch):
    monkeypatch.setenv("JW_MEETING_HOME", str(tmp_path))
    runner = CliRunner()
    runner.invoke(app, ["congregation", "add", "norte", "--language", "es"])
    r = runner.invoke(app, ["list", "--congregation", "norte"])
    assert r.exit_code == 0
    assert "No programs" in r.stdout


def test_list_unknown_congregation_errors(tmp_path, monkeypatch):
    monkeypatch.setenv("JW_MEETING_HOME", str(tmp_path))
    runner = CliRunner()
    r = runner.invoke(app, ["list", "--congregation", "nope"])
    assert r.exit_code == 1
