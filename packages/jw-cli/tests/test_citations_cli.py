"""Smoke test for `jw citations check` Typer command."""

from __future__ import annotations

import json
from pathlib import Path

from jw_cli.commands.citations import citations_app
from typer.testing import CliRunner

runner = CliRunner()


def test_cli_structural_with_urls(tmp_path: Path) -> None:
    urls_file = tmp_path / "u.txt"
    urls_file.write_text("https://wol.jw.org/es/wol/d/r4/lp-s/1\n", encoding="utf-8")
    result = runner.invoke(citations_app, ["check", "--urls", str(urls_file), "--report", "json"])
    assert result.exit_code == 0, result.stdout
    data = json.loads(result.stdout)
    assert data["mode"] == "structural"
    assert len(data["checks"]) == 1


def test_cli_rejects_both_inputs(tmp_path: Path) -> None:
    urls_file = tmp_path / "u.txt"
    urls_file.write_text("x", encoding="utf-8")
    out_file = tmp_path / "o.json"
    out_file.write_text("{}", encoding="utf-8")
    result = runner.invoke(
        citations_app,
        ["check", "--urls", str(urls_file), "--agent-output", str(out_file)],
    )
    assert result.exit_code != 0
