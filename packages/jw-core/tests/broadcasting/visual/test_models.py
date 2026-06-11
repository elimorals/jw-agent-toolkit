"""Visual broadcasting index Pydantic models."""

from __future__ import annotations

import pytest

from jw_core.broadcasting.visual.models import (
    IndexStats,
    VisualFrame,
    VisualSearchHit,
)


def test_visual_frame_minimal() -> None:
    f = VisualFrame(
        video_id="v1",
        timestamp_s=5.0,
        caption="A man teaching.",
        embedding_id=0,
    )
    assert f.ocr_text == ""
    assert f.thumb_path is None


def test_visual_frame_rejects_negative_timestamp() -> None:
    with pytest.raises(ValueError):
        VisualFrame(
            video_id="v1",
            timestamp_s=-1.0,
            caption="x",
            embedding_id=0,
        )


def test_search_hit_round_trip() -> None:
    hit = VisualSearchHit(
        video_id="v1",
        timestamp_s=10.5,
        score=0.42,
        source="hybrid",
        caption="x",
        deep_link="https://tv.jw.org/x#t=10",
    )
    dumped = hit.model_dump()
    rehydrated = VisualSearchHit.model_validate(dumped)
    assert rehydrated.source == "hybrid"


def test_search_hit_rejects_unknown_source() -> None:
    with pytest.raises(ValueError):
        VisualSearchHit(
            video_id="v1",
            timestamp_s=0,
            score=0,
            source="garbage",  # type: ignore[arg-type]
            caption="x",
            deep_link="x",
        )


def test_index_stats() -> None:
    s = IndexStats(
        videos_indexed=3,
        frames_total=120,
        embeddings_dim=512,
        storage_mb=2.5,
        avg_frame_per_video=40.0,
    )
    assert s.frames_total == 120
