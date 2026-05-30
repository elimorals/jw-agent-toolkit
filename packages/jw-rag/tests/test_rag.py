"""Tests for jw-rag — uses FakeEmbedder so no API keys / network needed."""

from pathlib import Path

import pytest

from jw_rag import Chunk, FakeEmbedder, VectorStore, chunk_paragraphs
from jw_rag.retrieve import dedup_by_source, filter_by_metadata


# ── FakeEmbedder ────────────────────────────────────────────────────────

def test_fake_embedder_deterministic() -> None:
    emb = FakeEmbedder(dim=32)
    a = emb.embed(["hello"])
    b = emb.embed(["hello"])
    assert (a == b).all()


def test_fake_embedder_different_inputs_uncorrelated() -> None:
    emb = FakeEmbedder(dim=64)
    vecs = emb.embed(["hello", "world", "foo bar baz"])
    # Distinct inputs should not all be identical.
    sims = vecs @ vecs.T
    # Self-similarity ~1, cross-similarity should be much smaller.
    assert sims[0, 0] > 0.99
    assert abs(sims[0, 1]) < 0.5


def test_fake_embedder_normalized() -> None:
    import numpy as np
    emb = FakeEmbedder(dim=32)
    v = emb.embed(["test"])[0]
    assert abs(np.linalg.norm(v) - 1.0) < 1e-5


# ── Chunker ─────────────────────────────────────────────────────────────

def test_chunk_paragraphs_basic() -> None:
    paragraphs = [
        "Short paragraph one ending with period.",
        "Short paragraph two ending with period.",
        "Long paragraph three. It has more content here. Yes indeed.",
    ]
    chunks = chunk_paragraphs(paragraphs, "test-source", max_chars=500)
    assert len(chunks) >= 1
    for c in chunks:
        assert c.source_id == "test-source"
        assert c.id.startswith("test-source#")


def test_chunk_paragraphs_metadata_propagates() -> None:
    chunks = chunk_paragraphs(
        ["Hello."], "src", metadata={"book_num": 43, "chapter": 3}
    )
    assert chunks[0].metadata["book_num"] == 43
    assert chunks[0].metadata["chapter"] == 3


def test_chunk_paragraphs_splits_long_paragraph() -> None:
    very_long = "Sentence one is short. " * 200  # ~4400 chars
    chunks = chunk_paragraphs([very_long], "src", max_chars=500)
    assert len(chunks) > 1
    assert all(len(c.text) <= 510 for c in chunks)  # tiny slack for whitespace


# ── VectorStore: in-memory ──────────────────────────────────────────────

@pytest.fixture
def populated_store() -> VectorStore:
    emb = FakeEmbedder(dim=32)
    store = VectorStore(Path("/tmp/nonexistent"), emb)
    store.add([
        Chunk(id="c1", text="The love of God endures forever",
              source_id="ps:107", metadata={"book_num": 19, "chapter": 107}),
        Chunk(id="c2", text="Jesus said God so loved the world",
              source_id="jn:3", metadata={"book_num": 43, "chapter": 3}),
        Chunk(id="c3", text="Peace I leave with you my peace I give",
              source_id="jn:14", metadata={"book_num": 43, "chapter": 14}),
        Chunk(id="c4", text="A random unrelated sentence about cooking",
              source_id="cooking:1", metadata={"book_num": 0}),
    ])
    return store


def test_store_count(populated_store: VectorStore) -> None:
    assert populated_store.count == 4


def test_bm25_search_returns_relevant_first(populated_store: VectorStore) -> None:
    hits = populated_store.bm25_search("peace", top_k=2)
    assert hits[0].chunk.id == "c3"
    assert hits[0].source == "bm25"


def test_vector_search_returns_top_k(populated_store: VectorStore) -> None:
    hits = populated_store.vector_search("anything", top_k=2)
    assert len(hits) == 2
    assert hits[0].source == "vector"


def test_hybrid_search_combines_signals(populated_store: VectorStore) -> None:
    hits = populated_store.hybrid_search("peace", top_k=3)
    assert hits[0].source == "hybrid"
    ids = [h.chunk.id for h in hits]
    # 'peace' chunk should be in the top hits (BM25 boosts it).
    assert "c3" in ids[:2]


# ── Persistence ─────────────────────────────────────────────────────────

def test_store_save_and_load_roundtrip(tmp_path: Path) -> None:
    emb = FakeEmbedder(dim=16)
    store1 = VectorStore(tmp_path / "store", emb)
    store1.add([
        Chunk(id="x1", text="alpha", source_id="s", metadata={"k": 1}),
        Chunk(id="x2", text="beta", source_id="s", metadata={"k": 2}),
    ])
    store1.save()

    store2 = VectorStore(tmp_path / "store", emb)
    store2.load()
    assert store2.count == 2
    hits = store2.bm25_search("alpha", top_k=1)
    assert hits[0].chunk.id == "x1"


def test_store_load_rejects_dim_mismatch(tmp_path: Path) -> None:
    store_a = VectorStore(tmp_path / "store", FakeEmbedder(dim=16))
    store_a.add([Chunk(id="x", text="hi", source_id="s")])
    store_a.save()
    store_b = VectorStore(tmp_path / "store", FakeEmbedder(dim=32))
    with pytest.raises(ValueError, match="dim mismatch"):
        store_b.load()


# ── Retrieve helpers ───────────────────────────────────────────────────

def test_dedup_by_source(populated_store: VectorStore) -> None:
    # Add another chunk with same source_id to exercise dedup.
    populated_store.add([
        Chunk(id="c2b", text="Another John 3 chunk", source_id="jn:3"),
    ])
    hits = populated_store.bm25_search("john", top_k=10)
    deduped = dedup_by_source(hits)
    source_ids = [h.chunk.source_id for h in deduped]
    assert len(source_ids) == len(set(source_ids))


def test_filter_by_metadata(populated_store: VectorStore) -> None:
    hits = populated_store.bm25_search("god", top_k=10)
    filtered = filter_by_metadata(hits, book_num=43)
    assert all(h.chunk.metadata.get("book_num") == 43 for h in filtered)
