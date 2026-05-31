"""Tests for jw-mcp NLI integrations (Fase 39).

  1. New standalone tool ``evaluate_nli(claim, premise, language)`` returns
     {"verdict", "score", "provider"}.
  2. The ``apologetics`` MCP tool accepts an optional ``fidelity`` parameter
     and returns findings with nli_* metadata.

We do NOT hit the real network: the apologetics agent is patched out via
monkeypatch on the imported symbol. evaluate_nli uses FakeNLI by default.
"""

from __future__ import annotations

import asyncio

import pytest


@pytest.fixture(autouse=True)
def _force_fake_nli(monkeypatch) -> None:
    monkeypatch.setenv("JW_NLI_PROVIDER", "fake-nli")


def test_evaluate_nli_returns_verdict() -> None:
    from jw_mcp.server import evaluate_nli

    out = evaluate_nli(
        claim="God loves the world",
        premise="God so loved the world that he gave his only Son",
        language="en",
    )
    assert "verdict" in out
    assert "score" in out
    assert "provider" in out
    assert out["verdict"] in {"entails", "neutral", "contradicts"}
    assert 0.0 <= out["score"] <= 1.0
    assert out["provider"] == "fake-nli"


def test_evaluate_nli_default_language_is_en() -> None:
    from jw_mcp.server import evaluate_nli

    out = evaluate_nli(claim="a", premise="a")
    assert out["verdict"] in {"entails", "neutral", "contradicts"}


def test_evaluate_nli_handles_empty_inputs() -> None:
    from jw_mcp.server import evaluate_nli

    out = evaluate_nli(claim="", premise="")
    assert out["verdict"] in {"entails", "neutral", "contradicts"}
    assert 0.0 <= out["score"] <= 1.0


def test_apologetics_tool_accepts_fidelity_param(monkeypatch) -> None:
    """The MCP wrapper around apologetics exposes ``fidelity``."""
    from jw_agents.base import AgentResult, Citation, Finding
    from jw_mcp import server as srv

    async def fake(question, language="en", **_):  # noqa: ARG001
        return AgentResult(
            query=question,
            agent_name="apologetics",
            findings=[
                Finding(
                    summary="x",
                    excerpt="a sufficiently long excerpt for NLI evaluation here",
                    citation=Citation(url="https://wol.jw.org/x", title="t", kind="article"),
                )
            ],
            metadata={"language": language},
        )

    monkeypatch.setattr(srv, "apologetics_agent", fake)
    out = asyncio.run(
        srv.apologetics(question="?", language="en", use_rag=False, fidelity="warn")
    )
    assert "findings" in out
    assert out["findings"][0]["metadata"]["nli_verdict"] in {
        "entails",
        "neutral",
        "contradicts",
        "skipped",
    }


def test_apologetics_tool_fidelity_off_skips_metadata(monkeypatch) -> None:
    from jw_agents.base import AgentResult, Citation, Finding
    from jw_mcp import server as srv

    async def fake(question, language="en", **_):  # noqa: ARG001
        return AgentResult(
            query=question,
            agent_name="apologetics",
            findings=[
                Finding(
                    summary="x",
                    excerpt="a sufficiently long excerpt for NLI evaluation here",
                    citation=Citation(url="https://wol.jw.org/x", title="t", kind="article"),
                )
            ],
            metadata={"language": language},
        )

    monkeypatch.setattr(srv, "apologetics_agent", fake)
    out = asyncio.run(
        srv.apologetics(question="?", language="en", use_rag=False, fidelity="off")
    )
    assert "nli_verdict" not in out["findings"][0]["metadata"]
