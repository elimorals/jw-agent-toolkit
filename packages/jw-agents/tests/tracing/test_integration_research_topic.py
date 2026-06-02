"""research_topic emits cdn_search step and finding events per article."""

from __future__ import annotations

import pytest
from jw_agents.research_topic import research_topic
from jw_agents.tracing.schema import (
    FindingDroppedEvent,
    FindingKeptEvent,
    StepStartEvent,
)
from jw_agents.tracing.store import InMemoryTraceStore
from jw_agents.tracing.tracer import AgentTracer


class _FakeCdn:
    async def search(self, *_a, **_k):
        return {
            "results": [
                {"title": "A", "links": {"wol": "https://wol.jw.org/a"}},
                {"title": "B"},  # no links -> no url -> dropped
            ]
        }

    async def aclose(self) -> None:
        pass


class _FakeWol:
    async def fetch(self, *_a, **_k) -> str:
        # parse_article expects <p data-pid="N"> inside an <article>/#article
        # block. Anything else is silently skipped.
        return (
            "<html><body><div id='article'><h1>Article</h1>"
            "<p data-pid='1'>Body</p></div></body></html>"
        )

    async def aclose(self) -> None:
        pass


@pytest.mark.asyncio
async def test_research_topic_emits_kept_and_dropped() -> None:
    store = InMemoryTraceStore()
    tr = AgentTracer(agent="research_topic", store=store)
    with tr.run(input_kwargs={"topic": "Kingdom"}, language="en"):
        await research_topic(
            "Kingdom of God",
            language="E",
            cdn=_FakeCdn(),
            wol=_FakeWol(),
            trace=tr,
        )
    names = {e.name for e in store.events if isinstance(e, StepStartEvent)}
    assert "cdn_search" in names
    assert any(isinstance(e, FindingKeptEvent) for e in store.events)
    assert any(
        isinstance(e, FindingDroppedEvent) and e.reason == "no_url"
        for e in store.events
    )
    assert store.envelope is not None


@pytest.mark.asyncio
async def test_research_topic_without_trace_is_no_op() -> None:
    res = await research_topic(
        "Kingdom",
        language="E",
        cdn=_FakeCdn(),
        wol=_FakeWol(),
    )
    assert res.agent_name == "research_topic"
