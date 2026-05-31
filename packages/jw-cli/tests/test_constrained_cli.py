"""Tests for the jw constrained ask CLI command."""

from __future__ import annotations

import json

import pytest
from typer.testing import CliRunner


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


def test_constrained_ask_runs_with_fake_provider(
    runner: CliRunner, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("JW_LLM_PROVIDER", "fake")
    from jw_cli.main import app

    result = runner.invoke(
        app,
        [
            "constrained",
            "ask",
            "--agent",
            "verse_explainer",
            "--input",
            '{"reference":"John 3:16","language":"en"}',
            "--provider",
            "fake",
        ],
    )
    assert result.exit_code == 0, result.stdout + (result.stderr or "")
    # The CLI prints a JSON object (possibly multi-line). Find the JSON
    # block and parse it.
    out = result.stdout.strip()
    # We emit indent=2; everything from the first "{" to the last "}" is
    # our payload.
    start = out.find("{")
    end = out.rfind("}")
    assert start != -1 and end != -1, f"no JSON in output: {out!r}"
    payload = json.loads(out[start : end + 1])
    assert "findings" in payload


def test_constrained_ask_unknown_agent_fails(
    runner: CliRunner, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("JW_LLM_PROVIDER", "fake")
    from jw_cli.main import app

    result = runner.invoke(
        app,
        [
            "constrained",
            "ask",
            "--agent",
            "no_such_agent",
            "--input",
            "{}",
        ],
    )
    assert result.exit_code != 0
