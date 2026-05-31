"""Tests for the synth SQLite cache."""

from __future__ import annotations

from pathlib import Path

from jw_finetune.data.formats import QAPair
from jw_finetune.synth.cache import SynthCache, cache_key_for


def _pair(q: str = "Q?", a: str = "A.") -> QAPair:
    return QAPair(question=q, answer=a, source_chunk_id="c1", language="es", metadata={"k": "v"})


def test_cache_key_is_stable() -> None:
    k1 = cache_key_for(
        chunk_id="c1",
        chunk_text="hola",
        qa_style="doctrinal",
        language="es",
        n_pairs=3,
        provider_name="ollama",
        provider_model="llama3.1:8b",
    )
    k2 = cache_key_for(
        chunk_id="c1",
        chunk_text="hola",
        qa_style="doctrinal",
        language="es",
        n_pairs=3,
        provider_name="ollama",
        provider_model="llama3.1:8b",
    )
    assert k1 == k2


def test_cache_key_changes_with_text() -> None:
    k1 = cache_key_for(
        chunk_id="c1",
        chunk_text="hola",
        qa_style="doctrinal",
        language="es",
        n_pairs=3,
        provider_name="o",
        provider_model="m",
    )
    k2 = cache_key_for(
        chunk_id="c1",
        chunk_text="otro",
        qa_style="doctrinal",
        language="es",
        n_pairs=3,
        provider_name="o",
        provider_model="m",
    )
    assert k1 != k2


def test_cache_key_changes_with_style() -> None:
    base = dict(chunk_id="c1", chunk_text="t", language="es", n_pairs=3, provider_name="o", provider_model="m")
    k1 = cache_key_for(**base, qa_style="doctrinal")
    k2 = cache_key_for(**base, qa_style="verse-explain")
    assert k1 != k2


def test_cache_get_miss_returns_none(tmp_path: Path) -> None:
    cache = SynthCache(tmp_path / "c.db")
    assert cache.get("nonexistent") is None


def test_cache_put_then_get_returns_pairs(tmp_path: Path) -> None:
    cache = SynthCache(tmp_path / "c.db")
    pairs = [_pair("Q1?", "A1."), _pair("Q2?", "A2.")]
    cache.put("k1", pairs, chunk_id="c1", qa_style="doctrinal", language="es", provider="ollama")
    fetched = cache.get("k1")
    assert fetched is not None
    assert len(fetched) == 2
    assert fetched[0].question == "Q1?"
    assert fetched[1].answer == "A2."
    assert fetched[0].metadata.get("k") == "v"


def test_cache_overwrite(tmp_path: Path) -> None:
    cache = SynthCache(tmp_path / "c.db")
    cache.put("k1", [_pair("old", "old.")], chunk_id="c", qa_style="d", language="es", provider="o")
    cache.put("k1", [_pair("new", "new.")], chunk_id="c", qa_style="d", language="es", provider="o")
    pairs = cache.get("k1")
    assert pairs is not None
    assert pairs[0].question == "new"


def test_cache_stats(tmp_path: Path) -> None:
    cache = SynthCache(tmp_path / "c.db")
    assert cache.stats()["entries"] == 0
    cache.put("k1", [_pair("Q?", "A.")], chunk_id="c", qa_style="d", language="es", provider="o", n_rejected=2)
    s = cache.stats()
    assert s["entries"] == 1
    assert s["total_pairs"] == 1
    assert s["total_rejected"] == 2


def test_cache_clear(tmp_path: Path) -> None:
    cache = SynthCache(tmp_path / "c.db")
    cache.put("k1", [_pair()], chunk_id="c", qa_style="d", language="es", provider="o")
    cache.put("k2", [_pair()], chunk_id="c", qa_style="d", language="es", provider="o")
    cleared = cache.clear()
    assert cleared == 2
    assert cache.stats()["entries"] == 0
