"""Plan replay tests (Fase 65 post-MVP)."""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from jw_agents.meta.models import (
    OrchestrationPlan,
    OrchestrationResult,
    Step,
)
from jw_agents.meta.orchestrator import MetaOrchestrator
from jw_agents.meta.registry import clear_registry, register_tool


async def _ok_tool(query: str = "x") -> dict:
    return {
        "agent_name": "ok",
        "findings": [
            {
                "summary": query,
                "excerpt": f"text {query}",
                "citation": {"url": "https://wol.jw.org/x"},
                "kind": "verse",
            }
        ],
    }


@pytest.fixture(autouse=True)
def _setup() -> Iterator[None]:
    clear_registry()
    register_tool(
        name="research.topic",
        callable_=_ok_tool,
        description="r",
        args_schema={"query": "str"},
    )
    yield
    clear_registry()


class FakeLLM:
    name = "fake"

    async def acomplete(self, prompt: str) -> str:  # noqa: ARG002
        return '{"steps": []}'


@pytest.mark.asyncio
async def test_orchestrator_run_plan_executes_passed_plan() -> None:
    plan = OrchestrationPlan(
        goal="x",
        steps=[
            Step(
                id="step-1",
                tool="research.topic",
                args={"query": "soul"},
            )
        ],
    )
    orch = MetaOrchestrator(
        llm=FakeLLM(), nli=None, max_replans=0
    )
    result = await orch.run_plan(plan)
    assert isinstance(result, OrchestrationResult)
    assert len(result.step_results) == 1
    assert result.plan.steps[0].args["query"] == "soul"


@pytest.mark.asyncio
async def test_run_plan_round_trips_through_json() -> None:
    """Persisted plan JSON can be reloaded and executed."""
    import json

    plan = OrchestrationPlan(
        goal="x",
        steps=[
            Step(
                id="step-1",
                tool="research.topic",
                args={"query": "love"},
            )
        ],
    )
    dumped = plan.model_dump_json()
    rehydrated = OrchestrationPlan.model_validate(json.loads(dumped))
    orch = MetaOrchestrator(
        llm=FakeLLM(), nli=None, max_replans=0
    )
    result = await orch.run_plan(rehydrated)
    assert result.step_results[0].agent_result["findings"][0]["summary"] == "love"
