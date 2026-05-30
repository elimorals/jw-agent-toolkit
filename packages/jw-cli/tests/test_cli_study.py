from __future__ import annotations

from typer.testing import CliRunner

from jw_cli.main import app


runner = CliRunner()


def test_study_help_runs() -> None:
    result = runner.invoke(app, ["study", "--help"])
    assert result.exit_code == 0
    assert "study" in result.stdout.lower()


def test_study_goals_lists_taxonomy() -> None:
    result = runner.invoke(app, ["study", "goals"])
    assert result.exit_code == 0
    out = result.stdout
    assert "attend_meetings" in out
    assert "baptism" in out
    assert "drop_addiction_smoking" in out
