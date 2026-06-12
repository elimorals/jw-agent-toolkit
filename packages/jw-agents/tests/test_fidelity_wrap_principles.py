"""Tests for fidelity_wrap principles integration (F77 runtime).

We construct a fake NLI provider that always returns "entails" so NLI
checks pass cleanly and only the principle tier drives pass/fail
decisions. That isolates the new behaviour from the existing Phase 39
NLI logic.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import pytest
from jw_agents.base import AgentResult, Citation, Finding
from jw_agents.fidelity_wrap import fidelity_wrap
from jw_eval.principles import DetectionRules, Principle


@dataclass
class _FakeVerdict:
    verdict: Literal["entails", "neutral", "contradicts"]
    score: float
    provider: str = "fake"
    raw: dict[str, str] | None = None


class _AlwaysEntailsNLI:
    """Fake provider: any (claim, premise) entails with high confidence."""

    name = "fake-entails"
    target = "cpu"

    def is_available(self) -> bool:  # pragma: no cover - protocol shim
        return True

    def evaluate(self, *, claim: str, premise: str, language: str = "en") -> _FakeVerdict:
        return _FakeVerdict(verdict="entails", score=0.95)


def _principle_no_tobit() -> Principle:
    return Principle(
        id="PF-test-no-tobit",
        severity="hard",
        applies_to=["apologetics"],
        rationale="Apócrifos no son canónicos.",
        detect=DetectionRules(forbidden_phrases=["libro de tobías"]),
    )


def _principle_soft_warning() -> Principle:
    return Principle(
        id="PF-test-soft",
        severity="soft",
        applies_to=[],  # global
        rationale="Evitar fórmula vaga.",
        detect=DetectionRules(forbidden_phrases=["yo creo recordar"]),
    )


def _result_with(finding_text: str, agent: str = "apologetics") -> AgentResult:
    f = Finding(
        summary=finding_text,
        citation=Citation(url="https://wol.jw.org/x", title="t", kind="article"),
        excerpt=("Premisa larga suficiente para superar el minimo de 32 caracteres requerido por el wrapper."),
    )
    return AgentResult(query="q", agent_name=agent, findings=[f])


@pytest.mark.asyncio
async def test_hard_violation_rejected_when_on_fail_reject() -> None:
    @fidelity_wrap(
        on_fail="reject",
        provider=_AlwaysEntailsNLI(),  # type: ignore[arg-type]
        principles=[_principle_no_tobit()],
    )
    async def agent(q: str) -> AgentResult:
        return _result_with("Según el libro de Tobías la oración cura. Mateo 6:9 lo confirma.")

    result = await agent("x")
    assert result.findings == []
    assert any("Rejected" in w for w in result.warnings)
    assert any("PF-test-no-tobit" in w for w in result.warnings)


@pytest.mark.asyncio
async def test_hard_violation_warns_when_on_fail_warn() -> None:
    @fidelity_wrap(
        on_fail="warn",
        provider=_AlwaysEntailsNLI(),  # type: ignore[arg-type]
        principles=[_principle_no_tobit()],
    )
    async def agent(q: str) -> AgentResult:
        return _result_with("libro de Tobías enseña algo")

    result = await agent("x")
    assert len(result.findings) == 1
    assert any("PF-test-no-tobit" in w for w in result.warnings)


@pytest.mark.asyncio
async def test_no_violation_passes_through() -> None:
    @fidelity_wrap(
        on_fail="reject",
        provider=_AlwaysEntailsNLI(),  # type: ignore[arg-type]
        principles=[_principle_no_tobit()],
    )
    async def agent(q: str) -> AgentResult:
        return _result_with("Mateo 6:9 enseña la oración.")

    result = await agent("x")
    assert len(result.findings) == 1
    assert result.findings[0].metadata.get("principle_violations", "") == ""


@pytest.mark.asyncio
async def test_principle_scoped_by_agent_name_skips_unrelated_agent() -> None:
    """A principle that only applies to 'apologetics' must not fire for
    a different agent."""

    @fidelity_wrap(
        on_fail="reject",
        provider=_AlwaysEntailsNLI(),  # type: ignore[arg-type]
        principles=[_principle_no_tobit()],
    )
    async def agent(q: str) -> AgentResult:
        # Same offending text but agent is verse_explainer, not apologetics.
        return _result_with("libro de Tobías mencionado", agent="verse_explainer")

    result = await agent("x")
    assert len(result.findings) == 1  # not rejected — principle not scoped here


@pytest.mark.asyncio
async def test_soft_principle_never_rejects() -> None:
    @fidelity_wrap(
        on_fail="reject",
        provider=_AlwaysEntailsNLI(),  # type: ignore[arg-type]
        principles=[_principle_soft_warning()],
    )
    async def agent(q: str) -> AgentResult:
        return _result_with("yo creo recordar que dice algo")

    result = await agent("x")
    # Soft principle should annotate but not drop.
    assert len(result.findings) == 1
    assert "PF-test-soft" in result.findings[0].metadata.get("principle_soft", "")


@pytest.mark.asyncio
async def test_no_principles_keeps_old_behaviour() -> None:
    """Without `principles=`, fidelity_wrap should behave like Phase 39."""

    @fidelity_wrap(
        on_fail="reject",
        provider=_AlwaysEntailsNLI(),  # type: ignore[arg-type]
    )
    async def agent(q: str) -> AgentResult:
        return _result_with("anything")

    result = await agent("x")
    assert len(result.findings) == 1
    assert "fidelity_principles_count" not in result.metadata


@pytest.mark.asyncio
async def test_with_principles_records_count_in_metadata() -> None:
    @fidelity_wrap(
        on_fail="annotate_only",
        provider=_AlwaysEntailsNLI(),  # type: ignore[arg-type]
        principles=[_principle_no_tobit(), _principle_soft_warning()],
    )
    async def agent(q: str) -> AgentResult:
        return _result_with("anything")

    result = await agent("x")
    # Only one of the two principles is scoped to "apologetics"; the
    # soft one is global. So scoped count should be 2.
    assert result.metadata.get("fidelity_principles_count") == 2
