"""LLMChunker cache must short-circuit the provider on re-runs.

Acceptance: > 95 % hit rate on a 20-iteration loop with identical inputs.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from jw_rag.chunkers.fakes import FakeChunkerProvider
from jw_rag.chunkers.llm_chunker import LLMChunker


def test_cache_hit_skips_provider_call(tmp_path: Path) -> None:
    provider = FakeChunkerProvider(actions=[])
    chunker = LLMChunker(provider=provider, cache_dir=tmp_path, max_chars=200, min_chars=1)
    paragraphs = ["The first paragraph.", "The second paragraph."]

    chunker.chunk(paragraphs, source_id="doc-1", metadata={"language": "en"})
    assert len(provider.call_log) == 1

    chunker.chunk(paragraphs, source_id="doc-1", metadata={"language": "en"})
    assert len(provider.call_log) == 1, "second call should hit the cache"


def test_cache_miss_on_different_paragraphs(tmp_path: Path) -> None:
    provider = FakeChunkerProvider(actions=[])
    chunker = LLMChunker(provider=provider, cache_dir=tmp_path, max_chars=200, min_chars=1)

    chunker.chunk(["AA."], source_id="doc-2", metadata={"language": "en"})
    chunker.chunk(["BB."], source_id="doc-2", metadata={"language": "en"})
    assert len(provider.call_log) == 2


def test_cache_miss_on_different_provider_id(tmp_path: Path) -> None:
    p1 = FakeChunkerProvider(actions=[])
    p2 = FakeChunkerProvider(actions=[])
    p2.__class__ = type("OtherFake", (FakeChunkerProvider,), {"provider_id": "fake-2"})
    paragraphs = ["X."]

    c1 = LLMChunker(provider=p1, cache_dir=tmp_path, max_chars=200, min_chars=1)
    c1.chunk(paragraphs, source_id="d", metadata={"language": "en"})
    c2 = LLMChunker(provider=p2, cache_dir=tmp_path, max_chars=200, min_chars=1)
    c2.chunk(paragraphs, source_id="d", metadata={"language": "en"})

    assert len(p1.call_log) == 1
    assert len(p2.call_log) == 1


def test_hit_rate_over_95pct_on_repeated_inputs(tmp_path: Path) -> None:
    provider = FakeChunkerProvider(actions=[])
    chunker = LLMChunker(provider=provider, cache_dir=tmp_path, max_chars=200, min_chars=1)
    paragraphs = ["repeated content.", "consistent across runs."]
    N = 20
    for _ in range(N):
        chunker.chunk(paragraphs, source_id="hit-rate-doc", metadata={"language": "en"})
    hits = N - len(provider.call_log)
    rate = hits / N
    # First call is necessarily a miss; rate plateaus at (N-1)/N = 95% for N=20.
    assert rate >= 0.95, f"cache hit rate {rate:.1%} below 95%"


@pytest.mark.parametrize("env_var", ["JW_CHUNK_CACHE_DIR"])
def test_cache_dir_overridable_by_env(env_var: str, tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv(env_var, str(tmp_path / "custom"))
    provider = FakeChunkerProvider(actions=[])
    chunker = LLMChunker(provider=provider, max_chars=200, min_chars=1)
    chunker.chunk(["abc."], source_id="d", metadata={"language": "en"})
    assert (tmp_path / "custom").exists()
