"""Smoke tests for `jw reason` CLI."""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from jw_cli.commands.reason import reason_app

runner = CliRunner()


def test_cli_ask_runs_with_fake_llm() -> None:
    result = runner.invoke(reason_app, ["ask", "X", "-l", "es"])
    assert result.exit_code == 0, result.output
    parsed = json.loads(result.stdout)
    assert "steps" in parsed
    assert parsed["question_original"] == "X"


def test_cli_ask_export_md_writes_file(tmp_path: Path) -> None:
    out = tmp_path / "tree.md"
    result = runner.invoke(
        reason_app,
        ["ask", "X", "-l", "es", "--export", str(out)],
    )
    assert result.exit_code == 0, result.output
    assert out.exists()
    assert "Doctrinal reasoning" in out.read_text()


def test_cli_languages_lists_supported() -> None:
    result = runner.invoke(reason_app, ["languages"])
    assert result.exit_code == 0
    assert "es" in result.stdout
    assert "en" in result.stdout
    assert "pt" in result.stdout
