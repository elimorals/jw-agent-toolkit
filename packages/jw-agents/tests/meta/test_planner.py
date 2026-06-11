"""LLM planner tests (FakeLLMProvider, no network)."""

from __future__ import annotations

import json
from collections.abc import Iterator

import pytest

from jw_agents.meta.models import OrchestrationPlan
from jw_agents.meta.planner import Planner
from jw_agents.meta.registry import clear_registry, register_tool


async def _noop(**_: object) -> dict:
    return {"agent_name": "noop", "findings": []}


@pytest.fixture(autouse=True)
def _setup() -> Iterator[None]:
    clear_registry()
    register_tool(
        name="meeting.workbook",
        callable_=_noop,
        description="weekly workbook",
        args_schema={"language": "str"},
    )
    register_tool(
        name="meeting.public_talk_outline",
        callable_=_noop,
        description="talk outline",
        args_schema={"topic": "str"},
    )
    register_tool(
        name="export.study_sheet",
        callable_=_noop,
        description="export",
        args_schema={"format": "str"},
    )
    yield
    clear_registry()


class FakeLLMProvider:
    """Returns a pre-canned JSON string for a known goal pattern."""

    name = "fake"
    model = "fake-planner"

    def __init__(self, response_text: str) -> None:
        self._text = response_text
        self.calls = 0

    async def acomplete(self, prompt: str) -> str:
        self.calls += 1
        return self._text


@pytest.mark.asyncio
async def test_planner_returns_valid_plan_from_fake() -> None:
    response = json.dumps(
        {
            "goal": "prepara mi domingo",
            "language": "es",
            "steps": [
                {
                    "id": "step-1",
                    "tool": "meeting.workbook",
                    "args": {"language": "es"},
                    "depends_on": [],
                    "rationale": "descubrir programa de la semana",
                },
                {
                    "id": "step-2",
                    "tool": "meeting.public_talk_outline",
                    "args": {"topic": "amor"},
                    "depends_on": ["step-1"],
                    "rationale": "build outline from workbook hints",
                },
            ],
        }
    )
    planner = Planner(llm=FakeLLMProvider(response))
    plan = await planner.plan(goal="prepara mi domingo", language="es")
    assert isinstance(plan, OrchestrationPlan)
    assert len(plan.steps) == 2
    assert plan.steps[1].depends_on == ["step-1"]


@pytest.mark.asyncio
async def test_planner_rejects_unknown_tool() -> None:
    response = json.dumps(
        {
            "goal": "x",
            "language": "es",
            "steps": [
                {
                    "id": "s1",
                    "tool": "nope.does_not_exist",
                    "args": {},
                    "depends_on": [],
                    "rationale": "x",
                }
            ],
        }
    )
    planner = Planner(llm=FakeLLMProvider(response))
    with pytest.raises(ValueError, match="unknown tool"):
        await planner.plan(goal="x", language="es")


@pytest.mark.asyncio
async def test_planner_rejects_invalid_json() -> None:
    planner = Planner(llm=FakeLLMProvider("not json at all"))
    with pytest.raises(ValueError, match="invalid JSON"):
        await planner.plan(goal="x", language="es")


@pytest.mark.asyncio
async def test_planner_respects_max_steps_cap() -> None:
    steps = [
        {
            "id": f"s{i}",
            "tool": "meeting.workbook",
            "args": {},
            "depends_on": [],
            "rationale": "x",
        }
        for i in range(20)
    ]
    response = json.dumps({"goal": "x", "language": "es", "steps": steps})
    planner = Planner(llm=FakeLLMProvider(response), max_steps=5)
    with pytest.raises(ValueError, match="too many steps"):
        await planner.plan(goal="x", language="es")
