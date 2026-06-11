"""Smoke tests for the `jw spar` CLI."""

from __future__ import annotations

import json

from typer.testing import CliRunner

from jw_agents.spar.session import clear_sessions
from jw_cli.commands.spar import spar_app

runner = CliRunner()


def setup_function() -> None:
    clear_sessions()


def teardown_function() -> None:
    clear_sessions()


def test_cli_personas_lists_six() -> None:
    result = runner.invoke(spar_app, ["personas"])
    assert result.exit_code == 0
    for key in (
        "catholic",
        "evangelical",
        "atheist",
        "muslim",
        "nominal",
        "young_skeptic",
    ):
        assert key in result.stdout


def test_cli_start_prints_session_id() -> None:
    result = runner.invoke(
        spar_app, ["start", "--persona", "catholic", "--language", "es"]
    )
    assert result.exit_code == 0
    assert "spar-" in result.stdout


def test_cli_turn_returns_persona_response() -> None:
    start = runner.invoke(
        spar_app, ["start", "--persona", "catholic", "-l", "es"]
    )
    assert start.exit_code == 0
    sid = next(
        token for token in start.stdout.split() if token.startswith("spar-")
    )
    out = runner.invoke(spar_app, ["turn", sid, "Buenos días"])
    assert out.exit_code == 0
    assert '"reply"' in out.stdout


def test_cli_close_emits_feedback() -> None:
    start = runner.invoke(
        spar_app, ["start", "--persona", "atheist", "-l", "es"]
    )
    sid = next(
        token for token in start.stdout.split() if token.startswith("spar-")
    )
    runner.invoke(spar_app, ["turn", sid, "Hola, ¿podemos hablar?"])
    closed = runner.invoke(spar_app, ["close", sid])
    assert closed.exit_code == 0
    parsed = json.loads(closed.stdout)
    assert parsed["closed"] is True
    assert parsed["score_summary"] is not None
