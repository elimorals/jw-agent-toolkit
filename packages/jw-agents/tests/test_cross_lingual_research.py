"""F54.7 — tests for the cross_lingual_research agent.

Mocks `research_topic` + the translation provider so we don't hit jw.org or
load NLLB. Verifies the agent does the three steps in order and preserves
Bible refs across the translation hops.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from jw_agents.base import AgentResult, Citation, Finding
from jw_agents.cross_lingual_research import cross_lingual_research
from jw_core.translation_providers import TranslationProvider


class _RecordingTranslator(TranslationProvider):
    """Echo provider that records each call so the test can assert ordering."""

    name = "test-recording"
    is_commercial_safe = True

    def __init__(self) -> None:
        self.calls: list[tuple[str, str, str]] = []  # (text, src, tgt)

    def is_available(self) -> bool:
        return True

    def supports_language_pair(self, source: str, target: str) -> bool:
        return True

    def translate(self, text: str, *, source: str, target: str) -> str:
        self.calls.append((text, source, target))
        return f"[{source}->{target}] {text}"


@pytest.mark.asyncio
async def test_query_translated_then_corpus_searched_then_results_translated_back() -> None:
    """All three steps run, in order, with the right languages."""
    inner_findings = [
        Finding(
            summary="In John 3:16, God shows love.",
            citation=Citation(url="https://jw.org/en/article-1", title="Article 1"),
            excerpt="See John 3:16.",
        ),
    ]
    inner_result = AgentResult(query="day of Jehovah", agent_name="research_topic", findings=inner_findings)

    translator = _RecordingTranslator()

    with patch(
        "jw_agents.cross_lingual_research.research_topic",
        AsyncMock(return_value=inner_result),
    ) as mock_inner:
        out = await cross_lingual_research(
            "día de Jehová",
            user_language="es",
            corpus_language="E",
            corpus_language_iso="en",
            translator=translator,
        )

    # 1. Query was translated es → en before research.
    assert translator.calls[0] == ("día de Jehová", "es", "en")
    # 2. research_topic was called with the translated query.
    inner_call = mock_inner.call_args
    assert inner_call.args[0].startswith("[es->en]")
    # 3. Summary + excerpt translated en → es on the way back.
    en_to_es_calls = [c for c in translator.calls if c[1:] == ("en", "es")]
    assert len(en_to_es_calls) == 2  # one summary + one excerpt

    assert out.agent_name == "cross_lingual_research"
    assert out.metadata["translator"] == "test-recording"
    assert out.metadata["user_language"] == "es"
    assert out.metadata["corpus_language_iso"] == "en"
    assert len(out.findings) == 1
    assert out.findings[0].summary.startswith("[en->es]")
    # Citation URL is NOT translated — links stay intact.
    assert out.findings[0].citation.url == "https://jw.org/en/article-1"


@pytest.mark.asyncio
async def test_findings_without_excerpt_skip_excerpt_translation() -> None:
    inner = AgentResult(
        query="x", agent_name="research_topic",
        findings=[Finding(summary="bare", citation=Citation(url="u"), excerpt="")],
    )
    translator = _RecordingTranslator()
    with patch("jw_agents.cross_lingual_research.research_topic", AsyncMock(return_value=inner)):
        out = await cross_lingual_research("x", translator=translator)

    # Calls: 1 query translation, 1 summary translation. No excerpt call.
    assert len(translator.calls) == 2
    assert out.findings[0].excerpt == ""


@pytest.mark.asyncio
async def test_warnings_propagate_from_inner_result() -> None:
    inner = AgentResult(
        query="x", agent_name="research_topic", findings=[], warnings=["no results"],
    )
    translator = _RecordingTranslator()
    with patch("jw_agents.cross_lingual_research.research_topic", AsyncMock(return_value=inner)):
        out = await cross_lingual_research("x", translator=translator)
    assert out.warnings == ["no results"]
