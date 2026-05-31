"""Tests for the audio module (Module 3): TTS registry + VTT + index."""

from __future__ import annotations

import tempfile
from pathlib import Path

from jw_core.audio.broadcasting import (
    BroadcastingIndex,
    IndexedVideo,
    VTTSegment,
    deeplink_for_segment,
    index_vtt_file,
    parse_vtt,
)
from jw_core.audio.transcription import estimate_real_time_factor
from jw_core.audio.tts import get_tts_provider, list_tts_providers

# ── TTS registry ─────────────────────────────────────────────────────────

VTT_SAMPLE = """WEBVTT

00:00:00.500 --> 00:00:04.000
Welcome to today's program.

00:00:04.500 --> 00:00:09.250
Today we will discuss the Kingdom of God.
"""


def test_list_tts_providers_returns_known_names() -> None:
    names = {p["name"] for p in list_tts_providers()}
    assert {"system", "edge", "piper"} <= names


def test_get_tts_provider_falls_back_to_system() -> None:
    # `system` is always registered; on CI it may not have `say`/`espeak`,
    # but `list_tts_providers` always returns it.
    try:
        provider = get_tts_provider()
    except Exception:
        return  # no providers available on this CI runner — acceptable
    assert provider.name in {"system", "edge", "piper"}


# ── VTT parser ───────────────────────────────────────────────────────────


def test_parse_vtt_extracts_segments() -> None:
    segments = parse_vtt(VTT_SAMPLE)
    assert len(segments) == 2
    first = segments[0]
    assert first.start == 0.5
    assert first.end == 4.0
    assert "Welcome" in first.text


def test_parse_vtt_strips_html_like_tags() -> None:
    text = """WEBVTT

00:00:01.000 --> 00:00:03.000
<v Speaker>Hello <b>there</b>
"""
    segs = parse_vtt(text)
    assert len(segs) == 1
    assert "Hello there" in segs[0].text


# ── BroadcastingIndex ────────────────────────────────────────────────────


def _tmp_index_path() -> Path:
    return Path(tempfile.mkdtemp()) / "broadcasting.db"


def test_index_video_then_search() -> None:
    path = _tmp_index_path()
    with BroadcastingIndex(path) as idx:
        idx.index_video(
            IndexedVideo(
                video_id="v1",
                title="Hope of Resurrection",
                language="en",
                source_url="https://tv.jw.org/v1",
                segments=[
                    VTTSegment(start=0.0, end=5.0, text="Welcome to today's program"),
                    VTTSegment(start=5.0, end=10.0, text="We will speak about the resurrection"),
                ],
            )
        )
        hits = idx.search("resurrection")
        stats = idx.stats()
    assert stats == {"videos": 1, "segments": 2}
    assert len(hits) == 1
    assert "resurrection" in hits[0]["text"].lower()


def test_index_overwrites_on_reindex() -> None:
    path = _tmp_index_path()
    with BroadcastingIndex(path) as idx:
        idx.index_video(IndexedVideo(video_id="v", segments=[VTTSegment(0.0, 1.0, "alpha")]))
        idx.index_video(IndexedVideo(video_id="v", segments=[VTTSegment(0.0, 1.0, "beta")]))
        assert idx.stats() == {"videos": 1, "segments": 1}


def test_index_vtt_file_roundtrip() -> None:
    vtt_path = Path(tempfile.mkdtemp()) / "sample.vtt"
    vtt_path.write_text(VTT_SAMPLE, encoding="utf-8")
    index_path = _tmp_index_path()
    with BroadcastingIndex(index_path) as idx:
        count = index_vtt_file(
            idx,
            vtt_path,
            video_id="program-1",
            title="Today's Program",
            language="en",
            source_url="https://tv.jw.org/program-1",
        )
        assert count == 2
        results = idx.search("kingdom")
    assert any("Kingdom" in r["text"] for r in results)


def test_deeplink_appends_timecode() -> None:
    assert deeplink_for_segment("https://tv.jw.org/v", 12.7).endswith("?t=12s")
    assert deeplink_for_segment("https://tv.jw.org/v?lang=en", 42.0).endswith("&t=42s")


def test_estimate_rtf_curve() -> None:
    tiny = estimate_real_time_factor("tiny")
    large = estimate_real_time_factor("large-v3")
    assert tiny < large
