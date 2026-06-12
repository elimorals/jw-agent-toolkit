"""Tests for the F80.5 interpretability Tier 4 of fidelity_wrap.

The Tier 4 hook is observational: it must populate metadata for every
Finding but never veto a Finding. This keeps regression risk against the
F77 NLI + principles flow at zero.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from jw_agents.base import AgentResult, Finding
from jw_agents.fidelity_wrap import fidelity_wrap


# ---- Test doubles ----------------------------------------------------------


class _StubNLIProvider:
    name = "stub"

    def evaluate(self, *, claim: str, premise: str, language: str) -> Any:
        class V:
            verdict = "entails"
            score = 0.95
            provider = "stub"
        return V()


def _make_finding(summary: str, excerpt: str) -> Finding:
    from jw_agents.base import Citation

    return Finding(
        summary=summary,
        excerpt=excerpt,
        citation=Citation(
            url="https://wol.jw.org/x",
            title="w23 p10",
        ),
    )


def _make_result(findings: list[Finding]) -> AgentResult:
    return AgentResult(
        query="¿Qué enseña la Biblia?",
        agent_name="apologetics",
        findings=findings,
        metadata={"language": "es"},
    )


# ---- Tests -----------------------------------------------------------------


@pytest.mark.asyncio
async def test_no_evaluator_means_no_probe_metadata_added() -> None:
    @fidelity_wrap(provider=_StubNLIProvider())
    async def agent() -> AgentResult:
        return _make_result([_make_finding("una verdad", "un texto largo con suficientes caracteres aquí.")])

    result = await agent()
    f = result.findings[0]
    assert "probe_scores" not in f.metadata
    assert "probe_coherence" not in f.metadata
    assert "probe_tier4_enabled" not in result.metadata


@pytest.mark.asyncio
async def test_evaluator_called_and_metadata_stamped() -> None:
    captured: list[str] = []

    def evaluator(text: str) -> dict[str, float]:
        captured.append(text)
        return {"PF001-canon-only": 0.92, "PF002-cite": 0.41}

    @fidelity_wrap(provider=_StubNLIProvider(), probe_evaluator=evaluator)
    async def agent() -> AgentResult:
        return _make_result([_make_finding("una verdad", "un texto largo con suficientes caracteres aquí.")])

    result = await agent()
    assert len(captured) == 1, "evaluator should be called once per finding"
    f = result.findings[0]
    assert "probe_scores" in f.metadata
    scores = json.loads(f.metadata["probe_scores"])
    assert scores["PF001-canon-only"] == 0.92
    assert scores["PF002-cite"] == 0.41
    # default probe_min_score=0.5 → PF002 is a miss
    assert f.metadata["probe_misses"] == "PF002-cite"
    assert result.metadata.get("probe_tier4_enabled") == "true"


@pytest.mark.asyncio
async def test_coherence_clear_when_no_hard_and_no_miss() -> None:
    def evaluator(_text: str) -> dict[str, float]:
        return {"PF001-canon-only": 0.95}

    @fidelity_wrap(provider=_StubNLIProvider(), probe_evaluator=evaluator)
    async def agent() -> AgentResult:
        return _make_result([_make_finding("una verdad doctrinal", "texto largo válido y limpio.")])

    result = await agent()
    assert result.findings[0].metadata["probe_coherence"] == "clear"


@pytest.mark.asyncio
async def test_coherence_silent_when_probe_misses_but_no_hard() -> None:
    """The probe disagrees but the regex tier saw nothing — silent shortcut."""

    def evaluator(_text: str) -> dict[str, float]:
        return {"PF001-canon-only": 0.10}  # very low → miss

    @fidelity_wrap(provider=_StubNLIProvider(), probe_evaluator=evaluator)
    async def agent() -> AgentResult:
        return _make_result([_make_finding("una verdad doctrinal", "texto largo válido y limpio.")])

    result = await agent()
    f = result.findings[0]
    assert f.metadata["probe_coherence"] == "silent"
    assert "PF001-canon-only" in f.metadata["probe_misses"]


@pytest.mark.asyncio
async def test_evaluator_error_is_swallowed_and_annotated() -> None:
    def evaluator(_text: str) -> dict[str, float]:
        raise RuntimeError("model offline")

    @fidelity_wrap(provider=_StubNLIProvider(), probe_evaluator=evaluator)
    async def agent() -> AgentResult:
        return _make_result([_make_finding("una verdad", "un texto largo y suficiente.")])

    # Must NOT raise — Tier 4 errors are observational, not blocking.
    result = await agent()
    f = result.findings[0]
    assert f.metadata.get("probe_error") == "RuntimeError"
    assert "probe_scores" not in f.metadata


@pytest.mark.asyncio
async def test_probe_does_not_veto_kept_finding() -> None:
    """Even with all probes missing, the Finding must NOT be dropped."""

    def evaluator(_text: str) -> dict[str, float]:
        return {"PF001": 0.0, "PF002": 0.0}

    @fidelity_wrap(
        provider=_StubNLIProvider(),
        on_fail="reject",
        probe_evaluator=evaluator,
    )
    async def agent() -> AgentResult:
        return _make_result([_make_finding("una verdad", "un texto válido y suficiente.")])

    result = await agent()
    # NLI passed and no principles passed → finding stays kept regardless
    # of probe misses.
    assert len(result.findings) == 1
    assert result.findings[0].metadata["probe_coherence"] == "silent"


@pytest.mark.asyncio
async def test_custom_probe_min_score_threshold() -> None:
    def evaluator(_text: str) -> dict[str, float]:
        return {"PF001": 0.6, "PF002": 0.7}

    @fidelity_wrap(
        provider=_StubNLIProvider(),
        probe_evaluator=evaluator,
        probe_min_score=0.65,
    )
    async def agent() -> AgentResult:
        return _make_result([_make_finding("una verdad", "un texto largo y suficiente.")])

    result = await agent()
    f = result.findings[0]
    # PF001 < 0.65 → miss; PF002 ≥ 0.65 → not a miss
    assert f.metadata["probe_misses"] == "PF001"
    assert f.metadata["probe_min_score"] == "0.65"
