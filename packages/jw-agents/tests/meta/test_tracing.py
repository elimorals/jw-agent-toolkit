"""Tracing F43 integration in MetaOrchestrator (Fase 65 post-MVP)."""

from __future__ import annotations

import json
from collections.abc import Iterator

import pytest

from jw_agents.meta.orchestrator import MetaOrchestrator
from jw_agents.meta.registry import clear_registry, register_tool


async def _agent_finding(query: str = "x") -> dict:
    return {
        "agent_name": "fake",
        "findings": [
            {
                "summary": query,
                "excerpt": f"text about {query}",
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
        description="r",
        args_schema={"query": "str"},
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


@pytest.mark.asyncio
async def test_orchestrator_emits_meta_plan_step_critique_when_tracer_present() -> None:
    """When a tracer is passed, the orchestrator emits CustomEvent payloads
    named meta_plan / meta_step / meta_critique to its store."""
    from jw_agents.tracing.store import InMemoryTraceStore
    from jw_agents.tracing.tracer import AgentTracer

    store = InMemoryTraceStore()
    tracer = AgentTracer(agent="meta", store=store)
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
        llm=FakeLLM([plan_json]), nli=None, max_replans=0, tracer=tracer
    )
    await orch.run(goal="x", language="es")

    custom_event_names = [
        getattr(e, "name", None)
        for e in store.events
        if getattr(e, "type", None) == "custom"
    ]
    assert "meta_plan" in custom_event_names
    assert "meta_step" in custom_event_names
    assert "meta_critique" in custom_event_names


@pytest.mark.asyncio
async def test_orchestrator_without_tracer_emits_nothing() -> None:
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
    # Just verify it runs cleanly without tracer.
    orch = MetaOrchestrator(
        llm=FakeLLM([plan_json]), nli=None, max_replans=0, tracer=None
    )
    result = await orch.run(goal="x", language="es")
    assert result.trace_path is None
