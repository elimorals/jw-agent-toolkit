"""Real tool dispatcher tests (Fase 67 post-MVP).

We patch the actual agent imports to keep tests hermetic.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from jw_agents.reasoner.dispatchers import (
    _route_for,
    real_tool_dispatcher,
)
from jw_agents.reasoner.models import ReasoningStep


def test_route_for_verse_when_rationale_mentions_bible_get_verse() -> None:
    step = ReasoningStep(
        id="p1", kind="premise", statement="x",
        rationale="bible.get_verse para Juan 3",
    )
    assert _route_for(step) == "verse"


def test_route_for_topic_when_topic_index_in_hint() -> None:
    step = ReasoningStep(
        id="p1", kind="premise", statement="x",
        rationale="topic_index.search a Trinity",
    )
    assert _route_for(step) == "topic"


def test_route_for_apologetics_when_mentioned() -> None:
    step = ReasoningStep(
        id="p1", kind="premise", statement="x",
        rationale="invoca apologetics chain",
    )
    assert _route_for(step) == "apologetics"


def test_route_defaults_to_topic() -> None:
    step = ReasoningStep(
        id="p1", kind="premise", statement="x", rationale=""
    )
    assert _route_for(step) == "topic"


def _patch_research_topic(monkeypatch: pytest.MonkeyPatch, fn) -> None:
    """Patch the real module that `dispatchers.py` re-imports each call."""
    import sys

    mod = sys.modules["jw_agents.research_topic"]
    monkeypatch.setattr(mod, "research_topic", fn)


@pytest.mark.asyncio
async def test_dispatcher_returns_citation_from_research_topic(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_research_topic(topic: str, *, language: str = "E"):  # noqa: ARG001
        return SimpleNamespace(
            findings=[
                SimpleNamespace(
                    excerpt="amó tanto al mundo",
                    summary="John 3:16",
                    citation=SimpleNamespace(
                        url="https://wol.jw.org/x"
                    ),
                    kind="verse",
                )
            ]
        )

    _patch_research_topic(monkeypatch, fake_research_topic)
    step = ReasoningStep(
        id="p1",
        kind="premise",
        statement="amor universal",
        rationale="topic_index.search",
    )
    cit = await real_tool_dispatcher(step)
    assert cit is not None
    assert cit.wol_url == "https://wol.jw.org/x"
    assert cit.source_kind == "verse"


@pytest.mark.asyncio
async def test_dispatcher_returns_none_when_agent_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def boom(topic: str, *, language: str = "E"):  # noqa: ARG001
        raise RuntimeError("network down")

    _patch_research_topic(monkeypatch, boom)
    step = ReasoningStep(
        id="p1",
        kind="premise",
        statement="x",
        rationale="topic_index.search",
    )
    cit = await real_tool_dispatcher(step)
    assert cit is None


@pytest.mark.asyncio
async def test_dispatcher_returns_none_when_no_findings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def empty(topic: str, *, language: str = "E"):  # noqa: ARG001
        return SimpleNamespace(findings=[])

    _patch_research_topic(monkeypatch, empty)
    step = ReasoningStep(
        id="p1",
        kind="premise",
        statement="x",
        rationale="topic_index.search",
    )
    assert await real_tool_dispatcher(step) is None
