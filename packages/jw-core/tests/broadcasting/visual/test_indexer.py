"""VisualIndexer tests (Fase 69)."""

from __future__ import annotations

from pathlib import Path

import pytest

from jw_core.broadcasting.visual.indexer import VisualIndexer
from jw_core.broadcasting.visual.models import VisualFrame
from jw_core.broadcasting.visual.providers import (
    FakeCLIPEncoder,
    FakeVLMProvider,
)


def test_indexer_creates_storage_layout(tmp_path: Path) -> None:
    idx = VisualIndexer(tmp_path, embedding_dim=64)
    assert (tmp_path / "index.sqlite").exists()
    assert (tmp_path / "meta.json").exists()
    assert idx.stats().videos_indexed == 0
    idx.close()


def test_add_frame_assigns_id_and_persists(tmp_path: Path) -> None:
    idx = VisualIndexer(tmp_path, embedding_dim=64)
    clip = FakeCLIPEncoder(embedding_dim=64)
    eid = idx.add_frame(
        video_id="v1",
        timestamp_s=5.0,
        caption="A teaching scene.",
        embedding=clip.encode_text("teaching"),
    )
    assert eid == 1
    stats = idx.stats()
    assert stats.videos_indexed == 1
    assert stats.frames_total == 1
    assert stats.embeddings_dim == 64
    idx.close()


def test_add_frame_rejects_dim_mismatch(tmp_path: Path) -> None:
    idx = VisualIndexer(tmp_path, embedding_dim=64)
    with pytest.raises(ValueError, match="dim mismatch"):
        idx.add_frame(
            video_id="v1",
            timestamp_s=0.0,
            caption="x",
            embedding=[0.1] * 32,
        )


def test_load_vectors_stacks_correctly(tmp_path: Path) -> None:
    idx = VisualIndexer(tmp_path, embedding_dim=64)
    clip = FakeCLIPEncoder(embedding_dim=64)
    for ts in (0.0, 5.0, 10.0):
        idx.add_frame(
            video_id="v1",
            timestamp_s=ts,
            caption=f"frame-{ts}",
            embedding=clip.encode_text(f"frame-{ts}"),
        )
    vectors = idx.load_vectors()
    assert vectors.shape == (3, 64)
    idx.close()


def test_list_frames_filters_by_video(tmp_path: Path) -> None:
    idx = VisualIndexer(tmp_path, embedding_dim=64)
    clip = FakeCLIPEncoder(embedding_dim=64)
    for vid in ("v1", "v2"):
        for ts in (0.0, 5.0):
            idx.add_frame(
                video_id=vid,
                timestamp_s=ts,
                caption=f"{vid}-{ts}",
                embedding=clip.encode_text(f"{vid}-{ts}"),
            )
    only_v1 = idx.list_frames(video_id="v1")
    assert len(only_v1) == 2
    assert all(f.video_id == "v1" for f in only_v1)
    all_frames = idx.list_frames()
    assert len(all_frames) == 4
    idx.close()


def test_indexer_writes_meta_with_provider_names(tmp_path: Path) -> None:
    import json as _json

    VisualIndexer(
        tmp_path,
        embedding_dim=64,
        vlm_name="fake-vlm",
        clip_name="fake-clip",
    ).close()
    meta = _json.loads((tmp_path / "meta.json").read_text())
    assert meta["vlm_name"] == "fake-vlm"
    assert meta["clip_name"] == "fake-clip"
    assert meta["embedding_dim"] == 64


def test_indexer_round_trip_with_providers(tmp_path: Path) -> None:
    """Smoke: VLM + CLIP pipeline -> indexer -> list_frames."""
    idx = VisualIndexer(tmp_path, embedding_dim=64)
    vlm = FakeVLMProvider()
    clip = FakeCLIPEncoder(embedding_dim=64)
    image = b"fake-frame-bytes"
    caption = vlm.caption(image, language="es")
    emb = clip.encode_image(image)
    idx.add_frame(
        video_id="v1",
        timestamp_s=3.0,
        caption=caption,
        embedding=emb,
    )
    frames = idx.list_frames()
    assert len(frames) == 1
    assert frames[0].caption.startswith("image-")
    idx.close()
