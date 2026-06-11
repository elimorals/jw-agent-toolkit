"""Audience LLM scorer tests with fake provider."""

from __future__ import annotations

import pytest

from jw_core.talk_lab.models import TranscriptSegment
from jw_core.talk_lab.scorers.audience_llm import score_audience_warmth


class FakeLLM:
    def __init__(self, text: str) -> None:
        self._text = text

    async def acomplete(self, prompt: str) -> str:  # noqa: ARG002
        return self._text


def _ts(text: str) -> list[TranscriptSegment]:
    return [TranscriptSegment(speaker="A", text=text, start_s=0, end_s=1)]


@pytest.mark.asyncio
async def test_audience_warmth_with_fake_llm_returning_3() -> None:
    r = await score_audience_warmth(
        _ts("Hello dear friends, thank you for being here."),
        llm=FakeLLM("3"),
        language="en",
    )
    assert r.score == 3


@pytest.mark.asyncio
async def test_audience_warmth_with_garbage_llm_returns_0() -> None:
    r = await score_audience_warmth(
        _ts("Hello"), llm=FakeLLM("banana"), language="en"
    )
    assert r.score == 0


@pytest.mark.asyncio
async def test_audience_warmth_without_llm_fallback_heuristic() -> None:
    r = await score_audience_warmth(
        _ts("dear friends, thank you, brothers"),
        llm=None,
        language="en",
    )
    assert r.score >= 1


@pytest.mark.asyncio
async def test_audience_warmth_without_llm_cold_text() -> None:
    r = await score_audience_warmth(
        _ts("plain content no warmth markers"),
        llm=None,
        language="en",
    )
    assert r.score == 0
