"""Test the run_constrained MCP tool (Fase 35)."""

from __future__ import annotations

import pytest

from jw_agents.base import AgentResult, Citation, Finding


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


def test_run_constrained_tool_returns_agent_result_dict(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("JW_LLM_PROVIDER", "fake")

    # Stub the agent registry entry so we don't depend on network/state.
    from jw_mcp import server as _server

    real_resolver = _server._resolve_constrained_agent

    def _patched(name: str):  # type: ignore[no-untyped-def]
        if name == "verse_explainer":
            return lambda inp: _stub_verse_explainer(**{
                k: v
                for k, v in inp.items()
                if k in ("text", "language")
            })
        return real_resolver(name)

    monkeypatch.setattr(_server, "_resolve_constrained_agent", _patched)

    from jw_mcp.server import run_constrained

    out = run_constrained(
        agent_name="verse_explainer",
        input={"text": "John 3:16", "language": "en"},
        provider="fake",
    )
    assert isinstance(out, dict)
    assert "findings" in out
    assert all(
        f["citation"]["url"].startswith("https://wol.jw.org/")
        for f in out["findings"]
    )


def test_run_constrained_tool_rejects_unknown_agent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("JW_LLM_PROVIDER", "fake")
    from jw_mcp.server import run_constrained

    with pytest.raises(ValueError):
        run_constrained(
            agent_name="not_a_real_agent",
            input={},
            provider="fake",
        )
