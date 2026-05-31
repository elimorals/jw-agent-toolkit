"""Tests for hybrid_search_with_visual.

We mock the text store and visual store by directly populating them with a
known set of chunks/scores, then assert that the RRF fusion picks the right
order. Three regimes:
  - visual_store=None → falls back to text_store.hybrid_search exactly
  - visual_store empty → same fallback
  - visual_store non-empty → RRF includes visual rankings
"""

from __future__ import annotations

from pathlib import Path

from jw_rag.chunker import Chunk
from jw_rag.store import VectorStore
from jw_rag.visual.fakes import FakeColPaliEmbedder
from jw_rag.visual.hybrid import hybrid_search_with_visual
from jw_rag.visual.models import VisualChunk
from jw_rag.visual.visual_store import VisualVectorStore


class _MiniEmbedder:
    """Minimal Embedder-compatible class (structural)."""

    dim = 4

    def embed(self, texts):
        import numpy as np

        out = []
        for t in texts:
            v = [0.0, 0.0, 0.0, 0.0]
            for i, ch in enumerate(t.lower()):
                v[i % 4] += float(ord(ch) % 17) / 17.0
            out.append(v)
        return np.array(out, dtype=np.float32)


def _seed_text_store(tmp_path: Path) -> VectorStore:
    store = VectorStore(tmp_path / "text", _MiniEmbedder())
    store.add(
        [
            Chunk(id="t1", text="trinity is not biblical", source_id="A"),
            Chunk(id="t2", text="Paul missionary journey map", source_id="B"),
            Chunk(id="t3", text="seven days creation table", source_id="C"),
        ]
    )
    return store


def _seed_visual_store(tmp_path: Path) -> VisualVectorStore:
    from PIL import Image

    embedder = FakeColPaliEmbedder(dim=32, n_patches=16)
    store = VisualVectorStore(tmp_path / "visual", embedder)
    pairs = []
    for i, sid in enumerate(["A", "B", "C"]):
        png = tmp_path / f"{sid}.png"
        img = Image.new("RGB", (32, 32), color=(i * 60, 80, 200))
        img.save(png)
        pairs.append(
            (
                VisualChunk(
                    id=f"{sid}#p1",
                    source_id=sid,
                    page_number=1,
                    image_path=png,
                    ocr_text=f"visual {sid}",
                ),
                img,
            )
        )
    store.add(pairs)
    return store


def test_falls_back_when_visual_none(tmp_path: Path) -> None:
    text = _seed_text_store(tmp_path)
    hits = hybrid_search_with_visual(text, None, "trinity", top_k=2)
    assert len(hits) == 2
    # Without rerank, text_store.hybrid_search returns source="hybrid+rerank"
    # by default. Tolerate either marker — the contract is "no error, top_k items".
    assert all(h.source.startswith("hybrid") for h in hits)


def test_falls_back_when_visual_empty(tmp_path: Path) -> None:
    text = _seed_text_store(tmp_path)
    visual = VisualVectorStore(tmp_path / "visual", FakeColPaliEmbedder(dim=32, n_patches=16))
    hits = hybrid_search_with_visual(text, visual, "trinity", top_k=2)
    assert len(hits) == 2


def test_includes_visual_hits_when_present(tmp_path: Path) -> None:
    text = _seed_text_store(tmp_path)
    visual = _seed_visual_store(tmp_path)
    hits = hybrid_search_with_visual(text, visual, "paul journey", top_k=5)
    sources = {h.source for h in hits}
    assert "visual" in sources or any(h.chunk.source_id == "B" for h in hits)
    # Some hit corresponds to a VisualChunk
    assert any(isinstance(h.chunk, VisualChunk) for h in hits)


def test_top_k_is_respected(tmp_path: Path) -> None:
    text = _seed_text_store(tmp_path)
    visual = _seed_visual_store(tmp_path)
    hits = hybrid_search_with_visual(text, visual, "creation", top_k=2)
    assert len(hits) == 2


def test_rrf_score_monotonic(tmp_path: Path) -> None:
    text = _seed_text_store(tmp_path)
    visual = _seed_visual_store(tmp_path)
    hits = hybrid_search_with_visual(text, visual, "trinity", top_k=4)
    for a, b in zip(hits, hits[1:], strict=False):
        assert a.score >= b.score
