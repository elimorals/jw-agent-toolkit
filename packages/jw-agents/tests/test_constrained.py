"""Tests for run_with_citations — composition + reconciliation."""

from __future__ import annotations

import asyncio
import json

import pytest

from jw_agents.base import AgentResult, Citation, Finding
from jw_agents.constrained import CitationForgeryError, run_with_citations
from jw_core.grammar.fake import FakeConstrainedCaller


def _procedural_factory(urls: list[str]):
    async def fn(_inp: dict) -> AgentResult:
        return AgentResult(
            query="q",
            agent_name="t",
            findings=[
                Finding(
                    summary=f"procedural finding {i}",
                    citation=Citation(url=u, title="t", kind="article"),
                )
                for i, u in enumerate(urls)
            ],
        )

    return fn


def test_happy_path_returns_agent_result() -> None:
    procedural = _procedural_factory(["https://wol.jw.org/en/wol/d/r1/lp-e/2024001"])
    caller = FakeConstrainedCaller(
        seed=1, allowed_urls=["https://wol.jw.org/en/wol/d/r1/lp-e/2024001"]
    )
    res = asyncio.run(run_with_citations("question", agent=procedural, caller=caller))
    assert isinstance(res, AgentResult)
    assert all(f.citation.url.startswith("https://wol.jw.org/") for f in res.findings)


def test_reconciliation_rejects_forged_url() -> None:
    procedural = _procedural_factory(["https://wol.jw.org/en/wol/d/r1/lp-e/A"])
    forged = "https://wol.jw.org/en/wol/d/r1/lp-e/INVENTED"

    class _Forger:
        async def is_available(self) -> bool:
            return True

        async def generate(self, prompt: str, **_: object) -> str:
            return json.dumps(
                {
                    "query": prompt,
                    "agent_name": "t",
                    "findings": [
                        {
                            "summary": "x",
                            "citation": {"url": forged, "title": "", "kind": "article"},
                            "excerpt": "",
                        }
                    ],
                    "warnings": [],
                }
            )

    with pytest.raises(CitationForgeryError):
        asyncio.run(run_with_citations("q", agent=procedural, caller=_Forger()))


def test_uses_factory_when_caller_not_passed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JW_LLM_PROVIDER", "fake")
    procedural = _procedural_factory(["https://wol.jw.org/en/wol/d/r1/lp-e/X"])
    res = asyncio.run(run_with_citations("q", agent=procedural))
    assert res.findings


def test_empty_procedural_findings_short_circuits() -> None:
    async def empty(_: dict) -> AgentResult:
        return AgentResult(query="q", agent_name="t", findings=[])

    res = asyncio.run(run_with_citations("q", agent=empty, caller=FakeConstrainedCaller(seed=0)))
    # No procedural findings -> nothing to validate against, helper returns
    # the procedural result untouched plus a warning.
    assert res.findings == []
    assert any("no procedural findings" in w.lower() for w in res.warnings)
