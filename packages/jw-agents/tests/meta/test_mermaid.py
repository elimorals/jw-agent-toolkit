"""Mermaid export tests (Fase 65 post-MVP)."""

from __future__ import annotations

from jw_agents.meta.mermaid import plan_to_mermaid, result_to_mermaid
from jw_agents.meta.models import (
    CritiqueVerdict,
    OrchestrationPlan,
    OrchestrationResult,
    Step,
    StepResult,
)


def test_plan_to_mermaid_starts_with_flowchart() -> None:
    plan = OrchestrationPlan(
        goal="Prepara domingo",
        steps=[Step(id="s1", tool="meeting.workbook", args={})],
    )
    out = plan_to_mermaid(plan)
    assert out.splitlines()[0] == "flowchart TD"
    assert 'start((' in out
    assert "Prepara domingo" in out
    assert 's1["meeting.workbook"]' in out


def test_plan_to_mermaid_includes_dep_edges() -> None:
    plan = OrchestrationPlan(
        goal="x",
        steps=[
            Step(id="s1", tool="research.topic", args={}),
            Step(id="s2", tool="apologetics.research", args={}, depends_on=["s1"]),
        ],
    )
    out = plan_to_mermaid(plan)
    assert "s1 --> s2" in out
    # Only roots get an implicit start edge
    assert "start --> s1" in out
    assert "start --> s2" not in out


def test_plan_to_mermaid_escapes_quotes() -> None:
    plan = OrchestrationPlan(
        goal='Quote "test"',
        steps=[
            Step(
                id="s1",
                tool="x",
                args={},
                rationale='says "hello"',
            )
        ],
    )
    out = plan_to_mermaid(plan)
    # Internal quotes are replaced with single quotes; wrapper " stays
    assert '"test"' not in out
    assert "'test'" in out
    assert '"hello"' not in out
    assert "'hello'" in out


def test_plan_to_mermaid_truncates_long_labels() -> None:
    plan = OrchestrationPlan(
        goal="x",
        steps=[
            Step(
                id="s1",
                tool="t",
                args={},
                rationale="a" * 200,
            )
        ],
    )
    out = plan_to_mermaid(plan)
    assert "…" in out


def test_result_to_mermaid_colors_error_and_ok() -> None:
    plan = OrchestrationPlan(
        goal="x",
        steps=[
            Step(id="a", tool="t", args={}),
            Step(id="b", tool="t", args={}, depends_on=["a"]),
        ],
    )
    result = OrchestrationResult(
        plan=plan,
        step_results=[
            StepResult(step_id="a", agent_result={}, elapsed_ms=10),
            StepResult(
                step_id="b",
                agent_result={},
                error="boom",
                elapsed_ms=10,
            ),
        ],
        critique=CritiqueVerdict(overall_ok=False),
    )
    out = result_to_mermaid(result)
    assert "classDef error" in out
    assert "class a ok" in out
    assert "class b error" in out
