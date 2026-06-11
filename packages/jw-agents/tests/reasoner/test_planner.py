"""Planner tests (Fase 67)."""

from __future__ import annotations

import json

import pytest

from jw_agents.reasoner.planner import Planner


class FakeLLM:
    name = "fake"

    def __init__(self, text: str) -> None:
        self._text = text

    async def acomplete(self, prompt: str) -> str:  # noqa: ARG002
        return self._text


@pytest.mark.asyncio
async def test_planner_parses_valid_plan() -> None:
    payload = json.dumps(
        {
            "steps": [
                {
                    "id": "p1",
                    "kind": "premise",
                    "statement": "John 3:16 declares God's love.",
                    "depends_on": [],
                    "rationale": "...",
                },
                {
                    "id": "c1",
                    "kind": "conclusion",
                    "statement": "Therefore God's love motivates...",
                    "depends_on": ["p1"],
                    "rationale": "...",
                },
            ]
        }
    )
    planner = Planner(llm=FakeLLM(payload))
    steps = await planner.plan(question_normalized="x", language="es")
    assert [s.id for s in steps] == ["p1", "c1"]
    assert steps[1].depends_on == ["p1"]


@pytest.mark.asyncio
async def test_planner_rejects_invalid_json() -> None:
    planner = Planner(llm=FakeLLM("not json"))
    with pytest.raises(ValueError, match="invalid JSON"):
        await planner.plan(question_normalized="x", language="es")


@pytest.mark.asyncio
async def test_planner_rejects_unknown_kind() -> None:
    payload = json.dumps(
        {
            "steps": [
                {
                    "id": "p1",
                    "kind": "weird",
                    "statement": "x",
                    "depends_on": [],
                    "rationale": "x",
                }
            ]
        }
    )
    planner = Planner(llm=FakeLLM(payload))
    with pytest.raises(ValueError, match="invalid kind"):
        await planner.plan(question_normalized="x", language="es")


@pytest.mark.asyncio
async def test_planner_rejects_forward_reference() -> None:
    """Step depending on an id not yet defined must fail."""
    payload = json.dumps(
        {
            "steps": [
                {
                    "id": "i1",
                    "kind": "inference",
                    "statement": "x",
                    "depends_on": ["p1"],
                    "rationale": "x",
                }
            ]
        }
    )
    planner = Planner(llm=FakeLLM(payload))
    with pytest.raises(ValueError, match="unseen"):
        await planner.plan(question_normalized="x", language="es")


@pytest.mark.asyncio
async def test_planner_caps_max_steps() -> None:
    steps = [
        {
            "id": f"s{i}",
            "kind": "premise",
            "statement": "x",
            "depends_on": [],
            "rationale": "x",
        }
        for i in range(20)
    ]
    payload = json.dumps({"steps": steps})
    planner = Planner(llm=FakeLLM(payload), max_steps=5)
    with pytest.raises(ValueError, match="too many steps"):
        await planner.plan(question_normalized="x", language="es")
