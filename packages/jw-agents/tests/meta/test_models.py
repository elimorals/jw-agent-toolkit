"""Pydantic models for the meta-orchestrator."""

from __future__ import annotations

import pytest

from jw_agents.meta.models import (
    CritiqueVerdict,
    OrchestrationPlan,
    OrchestrationResult,
    Step,
    StepResult,
)


def test_step_minimal_pending() -> None:
    s = Step(id="step-1", tool="verse.explain", args={"reference": "John 3:16"})
    assert s.status == "pending"
    assert s.depends_on == []


def test_step_with_dependencies() -> None:
    s = Step(
        id="step-2",
        tool="apologetics.research",
        args={"question": "What is the soul?"},
        depends_on=["step-1"],
        rationale="Build on the prior verse context.",
    )
    assert s.depends_on == ["step-1"]
    assert s.rationale.startswith("Build on")


def test_plan_rejects_self_dep() -> None:
    with pytest.raises(ValueError):
        OrchestrationPlan(
            goal="x",
            steps=[Step(id="step-1", tool="x", args={}, depends_on=["step-1"])],
        )


def test_plan_rejects_missing_dep_target() -> None:
    with pytest.raises(ValueError):
        OrchestrationPlan(
            goal="x",
            steps=[Step(id="step-1", tool="x", args={}, depends_on=["step-99"])],
        )


def test_plan_accepts_valid_dag() -> None:
    plan = OrchestrationPlan(
        goal="prepare meeting",
        steps=[
            Step(id="step-1", tool="meeting.workbook", args={}),
            Step(
                id="step-2",
                tool="meeting.public_talk_outline",
                args={},
                depends_on=["step-1"],
            ),
        ],
    )
    assert len(plan.steps) == 2
    assert plan.plan_revision == 0


def test_step_result_pydantic() -> None:
    r = StepResult(
        step_id="step-1",
        agent_result={"findings": [], "agent_name": "verse_explainer"},
        elapsed_ms=42,
    )
    assert r.error is None
    assert r.tokens_used == 0


def test_critique_verdict_minimal() -> None:
    v = CritiqueVerdict(overall_ok=True, findings_per_step={"step-1": 5})
    assert v.suggested_replan is None
    assert v.nli_warnings == []


def test_orchestration_result_round_trip() -> None:
    plan = OrchestrationPlan(
        goal="x", steps=[Step(id="step-1", tool="t", args={})]
    )
    res = OrchestrationResult(
        plan=plan,
        step_results=[],
        critique=CritiqueVerdict(overall_ok=False, findings_per_step={}),
        consolidated_findings=[],
        total_elapsed_ms=0,
        total_tokens=0,
    )
    dumped = res.model_dump()
    rehydrated = OrchestrationResult.model_validate(dumped)
    assert rehydrated.plan.goal == "x"
