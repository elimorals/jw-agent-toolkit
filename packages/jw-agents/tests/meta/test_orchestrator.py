"""End-to-end MetaOrchestrator tests."""

from __future__ import annotations

import json
from collections.abc import Iterator

import pytest

from jw_agents.meta.models import OrchestrationResult
from jw_agents.meta.orchestrator import MetaOrchestrator
from jw_agents.meta.registry import clear_registry, register_tool


async def _agent_finding(query: str = "x") -> dict:
    return {
        "agent_name": "fake",
        "findings": [
            {
                "summary": query,
                "excerpt": f"some text about {query}",
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
        callable_=_agent_finding,
        description="research",
        args_schema={"query": "str"},
    )
    register_tool(
        name="verse.explain",
        callable_=_agent_finding,
        description="verse",
        args_schema={"reference": "str"},
    )
    yield
    clear_registry()


class FakeLLM:
    name = "fake"

    def __init__(self, responses: list[str]) -> None:
        self._responses = responses
        self._idx = 0

    async def acomplete(self, prompt: str) -> str:
        out = self._responses[self._idx]
        self._idx += 1
        return out


class FakeNLI:
    def evaluate_entailment(self, *, claim: str, premise: str) -> object:
        class V:
            verdict = "entails"
            score = 0.95

        return V()


@pytest.mark.asyncio
async def test_orchestrator_happy_path() -> None:
    plan_json = json.dumps(
        {
            "goal": "research soul",
            "language": "en",
            "steps": [
                {
                    "id": "step-1",
                    "tool": "research.topic",
                    "args": {"query": "soul"},
                    "depends_on": [],
                    "rationale": "find sources",
                }
            ],
        }
    )
    orch = MetaOrchestrator(
        llm=FakeLLM([plan_json]),
        nli=FakeNLI(),
        max_replans=0,
    )
    result = await orch.run(goal="research soul", language="en")
    assert isinstance(result, OrchestrationResult)
    assert len(result.step_results) == 1
    assert result.critique.overall_ok is True


@pytest.mark.asyncio
async def test_orchestrator_dry_run_returns_plan_only() -> None:
    plan_json = json.dumps(
        {
            "goal": "x",
            "language": "es",
            "steps": [
                {
                    "id": "step-1",
                    "tool": "research.topic",
                    "args": {"query": "x"},
                    "depends_on": [],
                    "rationale": "x",
                }
            ],
        }
    )
    orch = MetaOrchestrator(
        llm=FakeLLM([plan_json]), nli=None, max_replans=0
    )
    plan = await orch.plan_only(goal="x", language="es")
    assert plan.goal == "x"
    assert len(plan.steps) == 1


@pytest.mark.asyncio
async def test_orchestrator_replans_when_no_findings() -> None:
    async def _empty(**_: object) -> dict:
        return {"agent_name": "empty", "findings": []}

    register_tool(
        name="empty.tool",
        callable_=_empty,
        description="empty",
        args_schema={},
    )

    plan_a = json.dumps(
        {
            "goal": "x",
            "language": "en",
            "steps": [
                {
                    "id": "step-1",
                    "tool": "empty.tool",
                    "args": {},
                    "depends_on": [],
                    "rationale": "first",
                }
            ],
        }
    )
    orch = MetaOrchestrator(
        llm=FakeLLM([plan_a]), nli=None, max_replans=1
    )
    result = await orch.run(goal="x", language="en")
    # First plan emits empty findings -> critique triggers a replan
    # with a built-in `research.topic` suggested replan step.
    assert result.plan.plan_revision == 1
    assert any(s.tool == "research.topic" for s in result.plan.steps)


@pytest.mark.asyncio
async def test_orchestrator_respects_max_replans_zero() -> None:
    async def _empty(**_: object) -> dict:
        return {"agent_name": "empty", "findings": []}

    register_tool(
        name="empty.tool",
        callable_=_empty,
        description="empty",
        args_schema={},
    )

    plan_a = json.dumps(
        {
            "goal": "x",
            "language": "en",
            "steps": [
                {
                    "id": "step-1",
                    "tool": "empty.tool",
                    "args": {},
                    "depends_on": [],
                    "rationale": "first",
                }
            ],
        }
    )
    orch = MetaOrchestrator(
        llm=FakeLLM([plan_a]), nli=None, max_replans=0
    )
    result = await orch.run(goal="x", language="en")
    assert result.plan.plan_revision == 0
    assert result.critique.overall_ok is False
