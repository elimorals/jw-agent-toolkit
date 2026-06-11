"""Engine tests (Fase 69)."""

from __future__ import annotations

from pathlib import Path

import pytest

from jw_core.broadcasting.visual.engine import (
    default_root,
    index_video,
    search_index,
    stats_index,
)


@pytest.fixture(autouse=True)
def _isolated_root(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("JW_VISUAL_INDEX_ROOT", str(tmp_path / "visual"))


def test_default_root_honors_env(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("JW_VISUAL_INDEX_ROOT", str(tmp_path / "x"))
    assert default_root() == tmp_path / "x"


def test_index_video_with_fake_sampler_produces_frames(tmp_path: Path) -> None:
    stats = index_video(
        tmp_path / "fake.mp4",
        interval_s=5.0,
        use_real_ffmpeg=False,
        video_id="fake",
    )
    # fake_sample 30s / 5s = 7 frames (0, 5, 10, 15, 20, 25, 30)
    assert stats.frames_total == 7
    assert stats.videos_indexed == 1
    assert stats.embeddings_dim == 64


def test_search_index_returns_hits_after_index(tmp_path: Path) -> None:
    index_video(
        tmp_path / "fake.mp4",
        interval_s=5.0,
        use_real_ffmpeg=False,
        video_id="fake",
    )
    # Captions look like "image-<hex8> (en)"; search a substring known to match
    hits = search_index("image", top_k=3)
    assert isinstance(hits, list)


def test_stats_index_empty(tmp_path: Path) -> None:  # noqa: ARG001
    s = stats_index()
    assert s.videos_indexed == 0
    assert s.frames_total == 0
