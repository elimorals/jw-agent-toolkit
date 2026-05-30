"""Tests for the async synth orchestrator."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import pytest

from jw_finetune.synth.async_orchestrator import (
    AsyncSynthResult,
    synthesize_chunks_async,
)
from jw_finetune.synth.cache import SynthCache
from jw_finetune.synth.provider import LLMRequest, LLMResponse
from jw_rag.chunker import Chunk


@dataclass
class FakeProvider:
    response_text: str
    name: str = "fake"
    model: str = "f-1"

    def generate(self, req: LLMRequest) -> LLMResponse:
        return LLMResponse(
            text=self.response_text,
            provider=self.name, model=self.model,
            usage={"input_tokens": 5, "output_tokens": 10},
        )


def _chunk(idx: int) -> Chunk:
    return Chunk(
        id=f"w24:{idx}#0",
        text=f"Texto de prueba número {idx} suficientemente largo para SFT.",
        source_id=f"w24:{idx}",
        metadata={"language": "es", "pub_code": "w24"},
    )


@pytest.mark.asyncio
async def test_async_synth_basic(tmp_path: Path) -> None:
    cache = SynthCache(tmp_path / "c.db")
    valid_response = json.dumps({"pairs": [
        {"q": "¿Cuál es el propósito?",
         "a": "El propósito está claramente expuesto en las Escrituras."},
    ]})
    chunks = [_chunk(i) for i in range(3)]
    res = await synthesize_chunks_async(
        chunks,
        provider=FakeProvider(valid_response),
        qa_style="doctrinal",
        language="es",
        concurrency=2,
        cache=cache,
        n_pairs=1,
    )
    assert isinstance(res, AsyncSynthResult)
    assert res.total_chunks == 3
    assert len(res.pairs) == 3
    assert res.cache_hits == 0
    assert res.cache_misses == 3


@pytest.mark.asyncio
async def test_async_synth_uses_cache_on_rerun(tmp_path: Path) -> None:
    cache = SynthCache(tmp_path / "c.db")
    valid_response = json.dumps({"pairs": [
        {"q": "¿Qué representa?",
         "a": "Representa una verdad bíblica fundamental para los TJ."},
    ]})
    chunks = [_chunk(0), _chunk(1)]

    res1 = await synthesize_chunks_async(
        chunks, provider=FakeProvider(valid_response),
        qa_style="doctrinal", language="es",
        cache=cache, concurrency=2, n_pairs=1,
    )
    assert res1.cache_misses == 2

    # Second run should hit cache for all chunks.
    res2 = await synthesize_chunks_async(
        chunks, provider=FakeProvider(valid_response),
        qa_style="doctrinal", language="es",
        cache=cache, concurrency=2, n_pairs=1,
    )
    assert res2.cache_hits == 2
    assert res2.cache_misses == 0
    assert len(res2.pairs) == 2


@pytest.mark.asyncio
async def test_async_synth_progress_callback(tmp_path: Path) -> None:
    cache = SynthCache(tmp_path / "c.db")
    valid_response = json.dumps({"pairs": [
        {"q": "¿Qué es?",
         "a": "Es un concepto fundamental en la doctrina bíblica enseñada por los Testigos."},
    ]})
    chunks = [_chunk(i) for i in range(4)]
    progress_events: list[tuple[int, int, int]] = []

    def progress(done: int, total: int, pairs: int) -> None:
        progress_events.append((done, total, pairs))

    await synthesize_chunks_async(
        chunks, provider=FakeProvider(valid_response),
        qa_style="doctrinal", language="es",
        cache=cache, concurrency=2, n_pairs=1,
        progress=progress,
    )
    assert len(progress_events) == 4
    # Final call should report all done
    assert progress_events[-1][0] == 4
    assert progress_events[-1][1] == 4


@pytest.mark.asyncio
async def test_async_synth_handles_provider_failures(tmp_path: Path, monkeypatch) -> None:
    """Even if some chunks fail, others succeed and the result is partial."""
    monkeypatch.setattr("time.sleep", lambda _x: None)

    class FlakyProvider:
        name = "flaky"
        model = "f-1"
        def __init__(self):
            self.calls = 0
        def generate(self, req):
            self.calls += 1
            if self.calls % 3 == 0:
                raise ConnectionError("transient")
            return LLMResponse(
                text=json.dumps({"pairs": [
                    {"q": "¿Por qué?", "a": "Porque la Biblia lo enseña claramente en numerosos pasajes."}
                ]}),
                provider="flaky", model="f-1",
                usage={"input_tokens": 1, "output_tokens": 1},
            )

    cache = SynthCache(tmp_path / "c.db")
    chunks = [_chunk(i) for i in range(5)]
    res = await synthesize_chunks_async(
        chunks, provider=FlakyProvider(),
        qa_style="doctrinal", language="es",
        cache=cache, concurrency=2, n_pairs=1,
        max_retry_attempts=2,
    )
    # Some chunks succeed; some may fail entirely
    assert res.total_chunks == 5
    # Most likely all succeed because retry covers flakiness
    assert len(res.pairs) >= 3
