"""Tests for jw_rag.visual.models."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from jw_rag.visual.models import IngestResult, MultiVectorHit, VisualChunk


def test_visual_chunk_minimal() -> None:
    c = VisualChunk(
        id="abc#p1",
        source_id="abc",
        page_number=1,
        image_path=Path("/tmp/abc_p001.png"),
    )
    assert c.id == "abc#p1"
    assert c.ocr_text == ""
    assert c.metadata == {}


def test_visual_chunk_round_trip_dict() -> None:
    c = VisualChunk(
        id="abc#p2",
        source_id="abc",
        page_number=2,
        image_path=Path("/tmp/abc_p002.png"),
        ocr_text="foo",
        metadata={"language": "es"},
    )
    d = c.to_dict()
    assert d["page_number"] == 2
    assert d["image_path"] == "/tmp/abc_p002.png"
    back = VisualChunk.from_dict(d)
    assert back == c


def test_multi_vector_hit_score_field() -> None:
    chunk = VisualChunk(id="a#p1", source_id="a", page_number=1, image_path=Path("/tmp/x.png"))
    hit = MultiVectorHit(chunk=chunk, score=12.5, rank=1)
    assert hit.score == 12.5
    assert hit.rank == 1
    assert hit.source == "visual"


def test_ingest_result_addition() -> None:
    a = IngestResult(pages_added=3, pages_skipped=1, duration_ms=100)
    b = IngestResult(pages_added=2, pages_skipped=0, duration_ms=50)
    c = a + b
    assert c.pages_added == 5
    assert c.pages_skipped == 1
    assert c.duration_ms == 150


def test_visual_chunk_text_alias_for_ocr() -> None:
    """`.text` proxies to `ocr_text` so VisualChunk slots into SearchHit shape."""
    c = VisualChunk(
        id="x#1", source_id="x", page_number=1, image_path=Path("/tmp/x.png"), ocr_text="hello"
    )
    assert c.text == "hello"


def test_numpy_import_for_assertion_smoke() -> None:
    # Sanity check that numpy is available in tests (needed by store tests).
    arr = np.zeros((2, 3), dtype=np.float16)
    assert arr.shape == (2, 3)
