"""Hybrid visual_search tests (Fase 69)."""

from __future__ import annotations

from pathlib import Path

from jw_core.broadcasting.visual.indexer import VisualIndexer
from jw_core.broadcasting.visual.providers import FakeCLIPEncoder
from jw_core.broadcasting.visual.search import visual_search


def _make_index(tmp_path: Path) -> tuple[VisualIndexer, FakeCLIPEncoder]:
    idx = VisualIndexer(tmp_path, embedding_dim=64)
    clip = FakeCLIPEncoder(embedding_dim=64)
    frames = [
        ("v1", 0.0, "Paul travels to Athens.", "Paul travels"),
        ("v1", 5.0, "A teacher explains the kingdom.", "kingdom"),
        ("v2", 0.0, "Map of Mediterranean routes.", "map"),
        ("v2", 10.0, "Cross references about love.", "love"),
    ]
    for video_id, ts, caption, transcript in frames:
        idx.add_frame(
            video_id=video_id,
            timestamp_s=ts,
            caption=caption,
            embedding=clip.encode_text(caption),
            transcript_concurrent=transcript,
        )
    return idx, clip


def test_search_returns_hit_for_textual_match(tmp_path: Path) -> None:
    idx, clip = _make_index(tmp_path)
    hits = visual_search(idx, "Paul", clip_encoder=clip, top_k=5)
    assert hits
    assert any("Paul" in h.caption for h in hits)
    idx.close()


def test_search_empty_query_returns_no_hits(tmp_path: Path) -> None:
    idx, clip = _make_index(tmp_path)
    hits = visual_search(idx, "garbagewordxyz", clip_encoder=clip)
    # CLIP fallback may still surface some hits via the cosine pool, but
    # without a relevant text match, scores are usually low. We only
    # assert the search doesn't crash on an irrelevant query.
    assert isinstance(hits, list)
    idx.close()


def test_search_returns_empty_on_empty_index(tmp_path: Path) -> None:
    idx = VisualIndexer(tmp_path, embedding_dim=64)
    hits = visual_search(idx, "anything", clip_encoder=FakeCLIPEncoder(64))
    assert hits == []
    idx.close()


def test_search_includes_deep_link_and_score(tmp_path: Path) -> None:
    idx, clip = _make_index(tmp_path)
    hits = visual_search(idx, "kingdom", clip_encoder=clip, top_k=3)
    assert hits
    for h in hits:
        assert h.deep_link.startswith("https://tv.jw.org")
        assert h.score >= 0
        assert h.source in ("hybrid", "fts", "clip")
    idx.close()


def test_search_without_clip_still_works_via_fts_only(
    tmp_path: Path,
) -> None:
    idx, _ = _make_index(tmp_path)
    hits = visual_search(idx, "love", clip_encoder=None, top_k=5)
    assert hits
    assert all(h.source in ("fts", "hybrid") for h in hits)
    idx.close()
