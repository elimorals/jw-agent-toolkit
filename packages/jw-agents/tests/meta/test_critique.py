"""Critique stage tests — NLI verification and replan suggestion."""

from __future__ import annotations

from jw_agents.meta.critique import Critique
from jw_agents.meta.models import OrchestrationPlan, Step, StepResult


class FakeVerdict:
    def __init__(self, verdict: str, score: float = 0.9) -> None:
        self.verdict = verdict
        self.score = score


class FakeNLI:
    def __init__(self, verdict: str = "entails") -> None:
        self._verdict = verdict
        self.calls = 0

    def evaluate_entailment(self, *, claim: str, premise: str) -> FakeVerdict:
        self.calls += 1
        return FakeVerdict(self._verdict)


def _make_step_result(step_id: str, findings: list[dict]) -> StepResult:
    return StepResult(
        step_id=step_id,
        agent_result={"findings": findings, "agent_name": "t"},
        elapsed_ms=10,
    )


def test_critique_zero_findings_overall_not_ok() -> None:
    plan = OrchestrationPlan(goal="x", steps=[Step(id="a", tool="t", args={})])
    results = [_make_step_result("a", [])]
    verdict = Critique(nli=None).run(plan=plan, step_results=results)
    assert verdict.overall_ok is False
    assert verdict.suggested_replan is not None


def test_critique_all_entails_overall_ok() -> None:
    plan = OrchestrationPlan(goal="x", steps=[Step(id="a", tool="t", args={})])
    findings = [
        {
            "summary": "John 3:16",
            "excerpt": "amó tanto",
            "citation": {"url": "https://wol.jw.org/x"},
            "kind": "verse",
        },
        {
            "summary": "study",
            "excerpt": "world means humanity",
            "citation": {"url": "https://wol.jw.org/y"},
            "kind": "study_note",
        },
    ]
    results = [_make_step_result("a", findings)]
    verdict = Critique(nli=FakeNLI(verdict="entails")).run(
        plan=plan, step_results=results
    )
    assert verdict.overall_ok is True
    assert verdict.findings_per_step["a"] == 2


def test_critique_contradicts_majority_suggests_replan() -> None:
    plan = OrchestrationPlan(goal="x", steps=[Step(id="a", tool="t", args={})])
    findings = [
        {
            "summary": "X",
            "excerpt": "blah",
            "citation": {"url": "u"},
            "kind": "verse",
        },
        {
            "summary": "Y",
            "excerpt": "blah",
            "citation": {"url": "u"},
            "kind": "verse",
        },
    ]
    results = [_make_step_result("a", findings)]
    verdict = Critique(nli=FakeNLI(verdict="contradicts")).run(
        plan=plan, step_results=results
    )
    assert verdict.overall_ok is False
    assert len(verdict.nli_warnings) >= 1
    assert verdict.suggested_replan is not None


def test_critique_without_nli_provider_skips_nli_check() -> None:
    plan = OrchestrationPlan(goal="x", steps=[Step(id="a", tool="t", args={})])
    findings = [
        {
            "summary": "X",
            "excerpt": "blah",
            "citation": {"url": "u"},
            "kind": "verse",
        }
    ]
    results = [_make_step_result("a", findings)]
    verdict = Critique(nli=None).run(plan=plan, step_results=results)
    assert verdict.overall_ok is True
    assert verdict.nli_warnings == []
