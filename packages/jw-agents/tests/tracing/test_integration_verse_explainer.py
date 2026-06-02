"""verse_explainer emits one step per phase with kept events for each finding."""

from __future__ import annotations

import pytest
from jw_agents.tracing.schema import FindingKeptEvent, StepStartEvent
from jw_agents.tracing.store import InMemoryTraceStore
from jw_agents.tracing.tracer import AgentTracer
from jw_agents.verse_explainer import verse_explainer


class _FakeWol:
    async def get_bible_chapter(self, *_a, **_k):
        # Verse markup that get_verse/parse_verses recognises (Watchtower-style
        # span class="v" with id). Keeping it minimal but valid for English.
        html = (
            '<html><span class="v" id="v43-3-16-1">For God so loved the world.'
            "</span></html>"
        )
        return ("https://wol.jw.org/x", html)

    async def fetch(self, *_a, **_k) -> str:
        return "<html><h1>Article</h1></html>"

    async def aclose(self) -> None:
        pass


@pytest.mark.asyncio
async def test_verse_explainer_emits_steps_and_kept_events() -> None:
    store = InMemoryTraceStore()
    tr = AgentTracer(agent="verse_explainer", store=store)
    with tr.run(input_kwargs={"reference": "John 3:16"}, language="en"):
        await verse_explainer(
            "John 3:16",
            language="en",
            wol=_FakeWol(),
            trace=tr,
        )
    step_names = {e.name for e in store.events if isinstance(e, StepStartEvent)}
    assert "verse_fetch" in step_names
    # At least one kept event must fire (target_verses or chapter paragraphs).
    assert any(isinstance(e, FindingKeptEvent) for e in store.events)
    assert store.envelope is not None
    assert store.envelope.agent == "verse_explainer"


@pytest.mark.asyncio
async def test_verse_explainer_without_trace_is_no_op() -> None:
    res = await verse_explainer(
        "John 3:16",
        language="en",
        wol=_FakeWol(),
    )
    assert res.agent_name == "verse_explainer"
