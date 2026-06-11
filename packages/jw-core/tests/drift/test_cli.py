"""CLI smoke tests for `jw drift` (Fase 72)."""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from jw_cli.commands.drift import drift_app

runner = CliRunner()


def _write_jsonl(p: Path) -> None:
    lines = [
        {"text": "old", "year": 1985, "embedding": [1.0, 0.0]},
        {"text": "old2", "year": 1986, "embedding": [0.99, 0.05]},
        {"text": "old3", "year": 1987, "embedding": [1.0, 0.05]},
        {"text": "new", "year": 2024, "embedding": [0.0, 1.0]},
        {"text": "new2", "year": 2025, "embedding": [0.05, 0.99]},
        {"text": "new3", "year": 2026, "embedding": [0.0, 1.0]},
    ]
    p.write_text("\n".join(json.dumps(d) for d in lines))


def test_cli_eras_lists_decades() -> None:
    result = runner.invoke(drift_app, ["eras"])
    assert result.exit_code == 0
    assert "1900s" in result.stdout
    assert "2020s" in result.stdout


def test_cli_note_es() -> None:
    result = runner.invoke(drift_app, ["note", "-l", "es"])
    assert result.exit_code == 0
    assert "Proverbios 4:18" in result.stdout


def test_cli_analyze_detects_drift(tmp_path: Path) -> None:
    chunks_path = tmp_path / "chunks.jsonl"
    _write_jsonl(chunks_path)
    result = runner.invoke(
        drift_app,
        ["analyze", "alma", "--chunks", str(chunks_path), "-l", "es"],
    )
    assert result.exit_code == 0, result.output
    parsed = json.loads(result.stdout)
    assert parsed["insufficient_data"] is False
    assert parsed["drift_events"]
