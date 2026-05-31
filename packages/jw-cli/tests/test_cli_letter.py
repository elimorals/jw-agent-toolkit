"""Smoke tests for `jw letter` CLI."""

from __future__ import annotations

from jw_cli.main import app
from typer.testing import CliRunner

runner = CliRunner()


def test_letter_cli_letter_kind_runs() -> None:
    result = runner.invoke(
        app,
        [
            "letter",
            "--kind",
            "letter",
            "--topic",
            "esperanza para una madre en duelo",
            "--audience",
            "grieving",
            "--lang",
            "es",
        ],
    )
    assert result.exit_code == 0, result.output
    assert "opener" in result.output.lower()
    assert "bridge" in result.output.lower()
    assert "scripture" in result.output.lower()
    assert "closing" in result.output.lower()


def test_letter_cli_phone_kind_shows_time_target() -> None:
    result = runner.invoke(
        app,
        ["letter", "--kind", "phone", "--topic", "paz", "--lang", "es"],
    )
    assert result.exit_code == 0
    assert "75" in result.output  # time target seconds


def test_letter_cli_invalid_kind_exits_nonzero() -> None:
    result = runner.invoke(
        app,
        ["letter", "--kind", "email", "--topic", "x"],
    )
    assert result.exit_code != 0


def test_letter_cli_territory_hint_appears_in_output() -> None:
    result = runner.invoke(
        app,
        [
            "letter",
            "--kind",
            "letter",
            "--topic",
            "esperanza",
            "--lang",
            "es",
            "--territory",
            "Lima, Perú",
        ],
    )
    assert result.exit_code == 0
    assert "Lima, Perú" in result.output
