"""Frame sampler tests (Fase 69)."""

from __future__ import annotations

from pathlib import Path

import pytest

from jw_core.broadcasting.visual.sampler import (
    FrameSamplerError,
    fake_sample,
    sample_frames,
)


def test_fake_sample_yields_expected_count() -> None:
    frames = list(fake_sample(duration_s=10.0, interval_s=5.0))
    # 0, 5, 10 -> 3 frames
    assert len(frames) == 3
    assert frames[0][0] == 0.0
    assert frames[-1][0] == 10.0


def test_fake_sample_each_frame_has_distinct_bytes() -> None:
    frames = list(fake_sample(duration_s=20.0, interval_s=5.0))
    payloads = {b for _, b in frames}
    assert len(payloads) == len(frames)


def test_sample_frames_missing_file_raises(tmp_path: Path) -> None:
    """Even when ffmpeg is on PATH, a missing video raises clearly."""
    # We bypass `ffmpeg_available()` by passing a missing path: the
    # sampler raises FrameSamplerError before invoking ffmpeg if ffmpeg
    # is absent OR if the file does not exist.
    with pytest.raises(FrameSamplerError):
        next(iter(sample_frames(tmp_path / "missing.mp4")))
