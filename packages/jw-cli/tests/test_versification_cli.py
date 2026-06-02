"""Smoke tests for ``jw versification`` subcommands."""

from __future__ import annotations

from jw_cli.main import app
from typer.testing import CliRunner


def test_versification_map_joel() -> None:
    runner = CliRunner()
    res = runner.invoke(
        app, ["versification", "map", "Joel 2:28", "--to", "masoretic"]
    )
    assert res.exit_code == 0, res.output
    assert "Joel" in res.output
    assert "3:1" in res.output


def test_versification_explain_psalm() -> None:
    runner = CliRunner()
    res = runner.invoke(
        app,
        [
            "versification",
            "explain",
            "Psalms 51:1",
            "--to",
            "lxx",
            "--lang",
            "es",
        ],
    )
    assert res.exit_code == 0, res.output
    # Either the localized prose (Salmo 50) or the fallback identity message
    assert "Salmo" in res.output or "discrepancy" in res.output.lower()


def test_versification_list_filtered() -> None:
    runner = CliRunner()
    res = runner.invoke(app, ["versification", "list", "--book", "Joel"])
    assert res.exit_code == 0, res.output
    assert "Joel" in res.output
