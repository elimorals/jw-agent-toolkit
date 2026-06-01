"""Smoke tests for `jw brain` subcommand integration."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from jw_brain.cli import brain_app

runner = CliRunner()


def test_brain_help_lists_subcommands() -> None:
    result = runner.invoke(brain_app, ["--help"])
    assert result.exit_code == 0
    for cmd in ("init", "compile", "query", "lint", "status", "snapshot"):
        assert cmd in result.stdout


def test_brain_init_creates_structure(tmp_path: Path) -> None:
    brain = tmp_path / "test-brain"
    result = runner.invoke(brain_app, ["init", "--brain", str(brain), "--domain", "tj"])
    assert result.exit_code == 0, result.stdout
    assert (brain / "config.toml").exists()
    assert (brain / "raw" / "inbox").exists()
    assert (brain / "vault" / ".obsidian").exists()
    assert (brain / "graph").exists()


def test_brain_status_reports_empty_graph(tmp_path: Path) -> None:
    brain = tmp_path / "test-brain"
    runner.invoke(brain_app, ["init", "--brain", str(brain), "--domain", "tj"])
    result = runner.invoke(brain_app, ["status", "--brain", str(brain)])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["graph"]["n_nodes"] == 0
    assert data["raw"]["pending"] == 0


def test_brain_status_fails_without_config(tmp_path: Path) -> None:
    result = runner.invoke(brain_app, ["status", "--brain", str(tmp_path / "nonexistent")])
    assert result.exit_code == 2


def test_brain_compile_dry_run_on_empty_inbox(tmp_path: Path) -> None:
    brain = tmp_path / "test-brain"
    runner.invoke(brain_app, ["init", "--brain", str(brain)])
    result = runner.invoke(brain_app, ["compile", "--brain", str(brain), "--dry-run"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["dry_run"] is True
    assert data["n_files_processed"] == 0


def test_brain_compile_e2e_md_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """End-to-end: init, drop a markdown file, compile, verify graph populated."""

    monkeypatch.setenv("JW_GEN_PROVIDER", "fake")
    brain = tmp_path / "test-brain"
    runner.invoke(brain_app, ["init", "--brain", str(brain)])
    (brain / "raw" / "inbox" / "note.md").write_text(
        "Reflexión sobre Juan 3:16.", encoding="utf-8"
    )

    result = runner.invoke(brain_app, ["compile", "--brain", str(brain)])
    assert result.exit_code == 0, result.stdout
    data = json.loads(result.stdout)
    assert data["n_files_processed"] == 1


def test_brain_snapshot_creates_tar(tmp_path: Path) -> None:
    brain = tmp_path / "test-brain"
    runner.invoke(brain_app, ["init", "--brain", str(brain)])
    result = runner.invoke(brain_app, ["snapshot", "--brain", str(brain), "--label", "pre-test"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    snap_path = Path(data["snapshot"])
    assert snap_path.exists()
    assert "pre-test" in snap_path.name


def test_brain_lint_empty(tmp_path: Path) -> None:
    brain = tmp_path / "test-brain"
    runner.invoke(brain_app, ["init", "--brain", str(brain)])
    result = runner.invoke(brain_app, ["lint", "--brain", str(brain)])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["orphan_count"] == 0
