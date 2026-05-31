"""Tests for the jw constrained ask CLI command."""

from __future__ import annotations

import json

import pytest
from jw_agents.base import AgentResult, Citation, Finding
from typer.testing import CliRunner


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


def _stub_verse_explainer(text: str = "", *, language: str = "en", **_: object) -> AgentResult:
    """Deterministic stand-in for verse_explainer — emits one WOL URL."""

    return AgentResult(
        query=text,
        agent_name="verse_explainer",
        findings=[
            Finding(
                summary=f"Stub finding for {text}",
                citation=Citation(
                    url="https://wol.jw.org/en/wol/b/r1/lp-e/nwt/43/3",
                    title="John 3",
                    kind="verse",
                ),
            )
        ],
    )


def test_constrained_ask_runs_with_fake_provider(runner: CliRunner, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JW_LLM_PROVIDER", "fake")

    # Stub the agent registry resolver so the test doesn't depend on
    # network state or real verse_explainer behavior.
    from jw_cli.commands import constrained as _constrained

    real_resolver = _constrained._agent_callable

    def _patched(name: str):  # type: ignore[no-untyped-def]
        if name == "verse_explainer":
            return lambda inp: _stub_verse_explainer(**{k: v for k, v in inp.items() if k in ("text", "language")})
        return real_resolver(name)

    monkeypatch.setattr(_constrained, "_agent_callable", _patched)

    from jw_cli.main import app

    result = runner.invoke(
        app,
        [
            "constrained",
            "ask",
            "--agent",
            "verse_explainer",
            "--input",
            '{"text":"John 3:16","language":"en"}',
            "--provider",
            "fake",
        ],
    )
    assert result.exit_code == 0, result.stdout + (result.stderr or "")
    out = result.stdout.strip()
    start = out.find("{")
    end = out.rfind("}")
    assert start != -1 and end != -1, f"no JSON in output: {out!r}"
    payload = json.loads(out[start : end + 1])
    assert "findings" in payload


def test_constrained_ask_unknown_agent_fails(runner: CliRunner, monkeypatch: pytest.MonkeyPatch) -> None:
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
