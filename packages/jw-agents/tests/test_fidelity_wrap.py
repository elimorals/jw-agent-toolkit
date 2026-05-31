"""Tests for the @fidelity_wrap decorator.

Contract:

  - Wraps an async function returning AgentResult.
  - For each Finding, evaluates NLI claim=summary vs premise=excerpt.
  - Stamps metadata: nli_verdict, nli_score, nli_provider.
  - Skip rule: excerpt < min_excerpt_chars → nli_verdict="skipped".
  - on_fail="warn"           → append AgentResult.warnings.
  - on_fail="reject"         → drop finding + warning.
  - on_fail="annotate_only"  → just metadata, no warnings.
  - Idempotent: applying twice doesn't duplicate metadata.
  - Stamps AgentResult.metadata["nli_min_score"] and ["nli_on_fail"].
"""

from __future__ import annotations

import asyncio

from jw_agents.base import AgentResult, Citation, Finding
from jw_agents.fidelity_wrap import fidelity_wrap
from jw_core.fidelity import NLIVerdict


def _result_with(findings: list[Finding]) -> AgentResult:
    return AgentResult(query="q", agent_name="x", findings=findings)


def _finding(summary: str, excerpt: str, url: str = "https://wol.jw.org/x") -> Finding:
    return Finding(
        summary=summary,
        excerpt=excerpt,
        citation=Citation(url=url, title="t", kind="article"),
    )


def _run(coro):
    return asyncio.run(coro)


class StubProvider:
    """Provider returning a configured verdict regardless of input."""

    name = "stub-nli"
    target = "cpu"

    def __init__(self, verdict: str, score: float) -> None:
        self._verdict = verdict
        self._score = score
        self.calls: list[tuple[str, str, str]] = []

    def is_available(self) -> bool:
        return True

    def evaluate(self, claim: str, premise: str, *, language: str = "en") -> NLIVerdict:
        self.calls.append((claim, premise, language))
        return NLIVerdict(verdict=self._verdict, score=self._score, provider=self.name, raw={})  # type: ignore[arg-type]


def test_warn_mode_keeps_finding_and_appends_warning() -> None:
    prov = StubProvider("contradicts", 0.4)
    base_finding = _finding(
        summary="The Trinity is a Bible teaching.",
        excerpt="The Trinity is not a Bible teaching, contrary to popular belief.",
    )

    @fidelity_wrap(min_score=0.7, on_fail="warn", provider=prov)
    async def agent(question: str) -> AgentResult:  # noqa: ARG001
        return _result_with([base_finding])

    r = _run(agent(question="?"))
    assert len(r.findings) == 1
    f = r.findings[0]
    assert f.metadata["nli_verdict"] == "contradicts"
    assert f.metadata["nli_score"] == 0.4
    assert f.metadata["nli_provider"] == "stub-nli"
    assert any("Low NLI fidelity" in w for w in r.warnings)
    assert r.metadata["nli_min_score"] == 0.7
    assert r.metadata["nli_on_fail"] == "warn"


def test_reject_mode_drops_finding() -> None:
    prov = StubProvider("contradicts", 0.4)

    @fidelity_wrap(min_score=0.7, on_fail="reject", provider=prov)
    async def agent() -> AgentResult:
        return _result_with([
            _finding(summary="bad", excerpt="this is a long enough premise text"),
        ])

    r = _run(agent())
    assert r.findings == []
    assert any("Rejected finding" in w for w in r.warnings)


def test_annotate_only_keeps_finding_no_warning() -> None:
    prov = StubProvider("contradicts", 0.2)

    @fidelity_wrap(min_score=0.7, on_fail="annotate_only", provider=prov)
    async def agent() -> AgentResult:
        return _result_with([
            _finding(summary="x", excerpt="this is a long enough premise text"),
        ])

    r = _run(agent())
    assert len(r.findings) == 1
    assert r.findings[0].metadata["nli_verdict"] == "contradicts"
    assert r.warnings == []


def test_pass_verdict_keeps_finding_no_warning() -> None:
    prov = StubProvider("entails", 0.95)

    @fidelity_wrap(min_score=0.7, on_fail="reject", provider=prov)
    async def agent() -> AgentResult:
        return _result_with([
            _finding(summary="x", excerpt="this is a long enough premise text"),
        ])

    r = _run(agent())
    assert len(r.findings) == 1
    assert r.warnings == []
    assert r.findings[0].metadata["nli_verdict"] == "entails"


def test_short_excerpt_is_skipped() -> None:
    prov = StubProvider("contradicts", 0.0)

    @fidelity_wrap(min_score=0.7, on_fail="reject", provider=prov, min_excerpt_chars=32)
    async def agent() -> AgentResult:
        return _result_with([_finding(summary="x", excerpt="Juan 3:16")])

    r = _run(agent())
    assert len(r.findings) == 1
    assert r.findings[0].metadata["nli_verdict"] == "skipped"
    # provider was NOT called for the short-excerpt finding
    assert prov.calls == []


def test_idempotent_does_not_re_evaluate() -> None:
    prov = StubProvider("entails", 0.9)

    @fidelity_wrap(min_score=0.7, provider=prov)
    @fidelity_wrap(min_score=0.7, provider=prov)
    async def agent() -> AgentResult:
        return _result_with([
            _finding(summary="x", excerpt="long enough excerpt for evaluation here"),
        ])

    r = _run(agent())
    assert len(r.findings) == 1
    # Provider called ONCE despite two layers of wrap.
    assert len(prov.calls) == 1


def test_default_provider_falls_back_to_factory(monkeypatch) -> None:
    # No ``provider`` kwarg → factory resolves FakeNLI when nothing else is wired.
    monkeypatch.setenv("JW_NLI_PROVIDER", "fake-nli")

    @fidelity_wrap(min_score=0.7)
    async def agent() -> AgentResult:
        return _result_with([
            _finding(
                summary="A test summary",
                excerpt="a totally different premise that has nothing in common with the claim",
            ),
        ])

    r = _run(agent())
    assert r.findings[0].metadata["nli_provider"] == "fake-nli"


def test_language_is_propagated_from_result_metadata() -> None:
    prov = StubProvider("entails", 0.9)

    @fidelity_wrap(min_score=0.7, provider=prov)
    async def agent() -> AgentResult:
        res = _result_with([
            _finding(summary="x", excerpt="long enough excerpt for evaluation here"),
        ])
        res.metadata["language"] = "pt"
        return res

    _run(agent())
    assert prov.calls[0][2] == "pt"


def test_concurrent_findings_each_get_metadata() -> None:
    prov = StubProvider("entails", 0.9)

    @fidelity_wrap(min_score=0.7, provider=prov)
    async def agent() -> AgentResult:
        return _result_with([
            _finding(summary=f"summary {i}", excerpt=f"long enough excerpt #{i} for eval")
            for i in range(5)
        ])

    r = _run(agent())
    assert len(r.findings) == 5
    for f in r.findings:
        assert "nli_verdict" in f.metadata
        assert "nli_score" in f.metadata
        assert "nli_provider" in f.metadata
