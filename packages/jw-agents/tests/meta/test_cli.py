"""Smoke tests for the `jw meta` CLI commands using typer.testing."""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from jw_cli.commands.meta import meta_app

runner = CliRunner()


def test_cli_tools_lists_builtin() -> None:
    result = runner.invoke(meta_app, ["tools"])
    assert result.exit_code == 0
    assert "research.topic" in result.stdout


def test_cli_plan_dry_run_with_fake_llm() -> None:
    result = runner.invoke(meta_app, ["plan", "test", "--language", "es"])
    assert result.exit_code == 0
    assert '"goal"' in result.stdout
    assert '"steps"' in result.stdout


def test_cli_plan_save_plan_writes_to_disk(tmp_path: Path) -> None:
    out = tmp_path / "plan.json"
    result = runner.invoke(
        meta_app, ["plan", "x", "-l", "es", "--save-plan", str(out)]
    )
    assert result.exit_code == 0
    assert out.exists()
    parsed = json.loads(out.read_text())
    assert "goal" in parsed
    assert "steps" in parsed


def test_cli_run_save_result_writes_to_disk(tmp_path: Path) -> None:
    out = tmp_path / "result.json"
    result = runner.invoke(
        meta_app, ["run", "x", "-l", "es", "--save-result", str(out)]
    )
    assert result.exit_code == 0
    assert out.exists()
    parsed = json.loads(out.read_text())
    assert "plan" in parsed
    assert "critique" in parsed
    assert "consolidated_findings" in parsed


def test_cli_run_trace_writes_jsonl(tmp_path: Path) -> None:
    trace_file = tmp_path / "trace.jsonl"
    result = runner.invoke(
        meta_app, ["run", "x", "-l", "es", "--trace", str(trace_file)]
    )
    assert result.exit_code == 0
    assert trace_file.exists()
    # At least one JSON object per line.
    lines = [
        line for line in trace_file.read_text().splitlines() if line.strip()
    ]
    assert lines
    for line in lines:
        json.loads(line)
