"""Verify the apologetics agent emits the expected trace events."""

from __future__ import annotations

from typing import Any

import pytest

from jw_agents.apologetics import apologetics
from jw_agents.tracing.schema import (
    FindingDroppedEvent,
    FindingKeptEvent,
)
from jw_agents.tracing.store import InMemoryTraceStore
from jw_agents.tracing.tracer import AgentTracer


class _FakeTopic:
    async def search_subjects(self, *_a, **_k) -> list[dict[str, Any]]:
        return [
            {
                "docid": "1001",
                "title": "Trinity",
                "snippet": "...",
                "wol_url": "https://wol.jw.org/topic/1001",
            },
            {
                "docid": None,
                "title": "No docid",
                "wol_url": None,
            },
        ]

    async def get_subject_page(self, *_a, **_k):
        class _Sub:
            title = "Trinity"
            total_citations = 1
            subheadings: list = []
            see_also: list = []
            docid = "1001"
            source_url = "https://wol.jw.org/topic/1001"

        return _Sub()

    async def aclose(self) -> None:
        pass


class _FakeWol:
    async def get_bible_chapter(self, *_a, **_k):
        return ("", "<html></html>")

    async def fetch(self, *_a, **_k) -> str:
        return "<html><h1>Title</h1></html>"

    async def aclose(self) -> None:
        pass


class _FakeCdn:
    async def search(self, *_a, **_k) -> dict[str, Any]:
        return {"results": []}

    async def aclose(self) -> None:
        pass


@pytest.mark.asyncio
async def test_apologetics_emits_step_and_finding_events() -> None:
    store = InMemoryTraceStore()
    tr = AgentTracer(agent="apologetics", store=store)
    with tr.run(input_kwargs={"question": "¿Trinidad?"}, language="es"):
        await apologetics(
            "¿Trinidad?",
            language="S",
            topic_top_k=2,
            topic=_FakeTopic(),
            cdn=_FakeCdn(),
            wol=_FakeWol(),
            trace=tr,
        )
    types = [type(e).__name__ for e in store.events]
    assert "StepStartEvent" in types
    assert "StepEndEvent" in types
    assert any(
        isinstance(e, FindingKeptEvent) and e.source == "topic_index"
        for e in store.events
    )
    assert any(
        isinstance(e, FindingDroppedEvent) and e.reason == "no_docid"
        for e in store.events
    )
    assert store.envelope is not None
    assert store.envelope.agent == "apologetics"
    assert store.envelope.findings_out >= 1


@pytest.mark.asyncio
async def test_apologetics_without_trace_is_no_op() -> None:
    res = await apologetics(
        "¿Trinidad?",
        language="S",
        topic=_FakeTopic(),
        cdn=_FakeCdn(),
        wol=_FakeWol(),
    )
    assert res.agent_name == "apologetics"
