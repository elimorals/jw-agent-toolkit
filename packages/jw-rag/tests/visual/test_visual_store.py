"""Tests for VisualVectorStore.

We use FakeColPaliEmbedder so MaxSim scores are deterministic. The store
is verified for: add(), search(), save()/load() round trip, mismatch
detection on load, idempotent re-add by source_id, and empty-store behavior.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from jw_rag.visual.errors import VisualStoreMismatchError
from jw_rag.visual.fakes import FakeColPaliEmbedder
from jw_rag.visual.models import VisualChunk
from jw_rag.visual.visual_store import VisualVectorStore


def _make_chunks(n: int, tmp_path: Path) -> list[tuple[VisualChunk, Image.Image]]:
    out: list[tuple[VisualChunk, Image.Image]] = []
    for i in range(n):
        img = Image.new("RGB", (64, 64), color=(i * 30, 50, 200 - i * 20))
        png = tmp_path / f"src1_p{i:03d}.png"
        img.save(png)
        chunk = VisualChunk(
            id=f"src1#p{i + 1}",
            source_id="src1",
            page_number=i + 1,
            image_path=png,
        )
        out.append((chunk, img))
    return out


def test_empty_store(tmp_path: Path) -> None:
    store = VisualVectorStore(tmp_path / "visual", FakeColPaliEmbedder(dim=64, n_patches=16))
    assert store.is_empty
    assert store.count == 0
    assert store.search("anything") == []


def test_add_and_search(tmp_path: Path) -> None:
    embedder = FakeColPaliEmbedder(dim=64, n_patches=16)
    store = VisualVectorStore(tmp_path / "visual", embedder)
    pairs = _make_chunks(3, tmp_path)
    store.add(pairs)
    assert store.count == 3
    hits = store.search("any query", top_k=2)
    assert len(hits) == 2
    assert hits[0].rank == 1
    assert hits[1].rank == 2
    assert hits[0].score >= hits[1].score
    # source field stays "visual" regardless of how we got there.
    assert all(h.source == "visual" for h in hits)


def test_add_idempotent_by_source_id(tmp_path: Path) -> None:
    embedder = FakeColPaliEmbedder(dim=64, n_patches=16)
    store = VisualVectorStore(tmp_path / "visual", embedder)
    pairs = _make_chunks(2, tmp_path)
    store.add(pairs)
    # Re-adding same chunks → no growth.
    store.add(pairs)
    assert store.count == 2


def test_source_ids(tmp_path: Path) -> None:
    embedder = FakeColPaliEmbedder(dim=64, n_patches=16)
    store = VisualVectorStore(tmp_path / "visual", embedder)
    store.add(_make_chunks(2, tmp_path))
    assert store.source_ids() == {"src1"}


def test_save_and_load_round_trip(tmp_path: Path) -> None:
    embedder = FakeColPaliEmbedder(dim=64, n_patches=16)
    store = VisualVectorStore(tmp_path / "visual", embedder)
    pairs = _make_chunks(3, tmp_path)
    store.add(pairs)
    pre_hits = store.search("q", top_k=3)
    store.save()

    store2 = VisualVectorStore(tmp_path / "visual", FakeColPaliEmbedder(dim=64, n_patches=16))
    store2.load()
    assert store2.count == 3
    post_hits = store2.search("q", top_k=3)
    assert [h.chunk.id for h in pre_hits] == [h.chunk.id for h in post_hits]
    for a, b in zip(pre_hits, post_hits, strict=True):
        assert abs(a.score - b.score) < 1e-3


def test_load_mismatch_raises(tmp_path: Path) -> None:
    store = VisualVectorStore(tmp_path / "visual", FakeColPaliEmbedder(dim=64, n_patches=16))
    store.add(_make_chunks(1, tmp_path))
    store.save()

    other = VisualVectorStore(tmp_path / "visual", FakeColPaliEmbedder(dim=64, n_patches=32))
    with pytest.raises(VisualStoreMismatchError):
        other.load()


def test_load_missing_dir_is_noop(tmp_path: Path) -> None:
    store = VisualVectorStore(tmp_path / "visual", FakeColPaliEmbedder(dim=64, n_patches=16))
    store.load()  # no meta.json present
    assert store.is_empty


def test_maxsim_score_is_sum_of_per_token_maxes(tmp_path: Path) -> None:
    """Sanity check: MaxSim equals our manual computation."""
    embedder = FakeColPaliEmbedder(dim=8, n_patches=4)
    store = VisualVectorStore(tmp_path / "visual", embedder)
    pairs = _make_chunks(1, tmp_path)
    store.add(pairs)
    q = embedder.embed_query("zero")
    d_vecs = embedder.embed_image(pairs[0][1]).astype(np.float32)
    sims = q.astype(np.float32) @ d_vecs.T
    expected = float(sims.max(axis=1).sum())
    hits = store.search("zero", top_k=1)
    assert abs(hits[0].score - expected) < 1e-3
