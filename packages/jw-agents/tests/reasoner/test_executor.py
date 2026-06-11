"""ReAct executor tests (Fase 67)."""

from __future__ import annotations

import pytest

from jw_agents.reasoner.executor import run_react_loop
from jw_agents.reasoner.models import Citation, ReasoningStep


class FakeVerdict:
    def __init__(self, verdict: str, score: float = 0.9) -> None:
        self.verdict = verdict
        self.score = score


class FakeNLI:
    name = "fake-nli"

    def __init__(self, verdict: str = "entails") -> None:
        self._verdict = verdict

    def evaluate_entailment(self, *, claim: str, premise: str) -> FakeVerdict:  # noqa: ARG002
        return FakeVerdict(self._verdict)


async def _citation_dispatcher(step: ReasoningStep) -> Citation | None:
    return Citation(
        text="amó tanto al mundo",
        wol_url="https://wol.jw.org/x",
        source_kind="verse",
    )


@pytest.mark.asyncio
async def test_executor_attaches_citation_and_entails() -> None:
    steps = [
        ReasoningStep(
            id="p1",
            kind="premise",
            statement="God's love is universal.",
        )
    ]
    tree = await run_react_loop(
        question_original="x",
        question_normalized="x",
        steps=steps,
        nli=FakeNLI("entails"),
        tool_dispatcher=_citation_dispatcher,
    )
    assert tree.steps[0].citation is not None
    assert tree.steps[0].nli_status == "entails"
    assert tree.truncated is False
    assert tree.nli_provider_used == "fake-nli"


@pytest.mark.asyncio
async def test_executor_truncates_on_contradicts_with_reject_mode() -> None:
    steps = [
        ReasoningStep(id="p1", kind="premise", statement="X"),
        ReasoningStep(
            id="p2", kind="premise", statement="Y", depends_on=["p1"]
        ),
    ]
    tree = await run_react_loop(
        question_original="x",
        question_normalized="x",
        steps=steps,
        nli=FakeNLI("contradicts"),
        nli_mode="reject",
        tool_dispatcher=_citation_dispatcher,
    )
    assert tree.truncated is True
    assert len(tree.steps) == 1
    assert tree.steps[0].nli_status == "contradicts"
    assert "truncated" in (tree.steps[0].rejected_reason or "")


@pytest.mark.asyncio
async def test_executor_warn_mode_keeps_contradicting_step() -> None:
    steps = [
        ReasoningStep(id="p1", kind="premise", statement="X"),
        ReasoningStep(
            id="p2", kind="premise", statement="Y", depends_on=["p1"]
        ),
    ]
    tree = await run_react_loop(
        question_original="x",
        question_normalized="x",
        steps=steps,
        nli=FakeNLI("contradicts"),
        nli_mode="warn",
        tool_dispatcher=_citation_dispatcher,
    )
    assert tree.truncated is False
    assert len(tree.steps) == 2
    assert tree.steps[0].nli_status == "contradicts"


@pytest.mark.asyncio
async def test_executor_no_citation_skips_nli() -> None:
    async def _empty(step: ReasoningStep) -> Citation | None:
        return None

    steps = [ReasoningStep(id="p1", kind="premise", statement="X")]
    tree = await run_react_loop(
        question_original="x",
        question_normalized="x",
        steps=steps,
        nli=FakeNLI("entails"),
        tool_dispatcher=_empty,
    )
    assert tree.steps[0].citation is None
    assert tree.steps[0].nli_status == "skipped"


@pytest.mark.asyncio
async def test_executor_no_nli_provider_skips() -> None:
    steps = [ReasoningStep(id="p1", kind="premise", statement="X")]
    tree = await run_react_loop(
        question_original="x",
        question_normalized="x",
        steps=steps,
        nli=None,
        tool_dispatcher=_citation_dispatcher,
    )
    assert tree.steps[0].citation is not None
    assert tree.steps[0].nli_status == "skipped"
    assert tree.nli_provider_used is None
