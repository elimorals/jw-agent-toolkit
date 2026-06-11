"""Pydantic models for talk_lab."""

from __future__ import annotations

import pytest

from jw_core.talk_lab.models import (
    CounselPointResult,
    ProsodyFeatures,
    TalkLabReport,
    WordTiming,
)


def test_prosody_round_trip() -> None:
    p = ProsodyFeatures(
        duration_s=30.0,
        speech_rate_wpm=140.0,
        pitch_mean_hz=180.0,
        pitch_range_hz=80.0,
        intensity_mean_db=-22.0,
        pause_count=5,
        pause_total_s=3.5,
        pause_avg_s=0.7,
        filler_count=2,
        filler_per_minute=4.0,
    )
    dumped = p.model_dump()
    rehydrated = ProsodyFeatures.model_validate(dumped)
    assert rehydrated.speech_rate_wpm == 140.0


def test_prosody_rejects_negative_durations() -> None:
    with pytest.raises(ValueError):
        ProsodyFeatures(
            duration_s=-1.0,
            speech_rate_wpm=140.0,
            pitch_mean_hz=180.0,
            pitch_range_hz=80.0,
            intensity_mean_db=-22.0,
            pause_count=0,
            pause_total_s=0.0,
            pause_avg_s=0.0,
            filler_count=0,
            filler_per_minute=0.0,
        )


def test_word_timing_rejects_inverted_window() -> None:
    with pytest.raises(ValueError):
        WordTiming(word="hello", start_s=1.0, end_s=0.5, confidence=0.9)


def test_counsel_score_in_range() -> None:
    c = CounselPointResult(
        point_id="cp-01",
        title="Pronunciation",
        title_localized="Pronunciación",
        score=2,
    )
    assert c.applies is True
    assert c.score == 2


def test_counsel_score_rejects_out_of_range() -> None:
    with pytest.raises(ValueError):
        CounselPointResult(
            point_id="cp-01",
            title="x",
            title_localized="x",
            score=5,
        )


def test_report_round_trip() -> None:
    p = ProsodyFeatures(
        duration_s=10.0,
        speech_rate_wpm=120.0,
        pitch_mean_hz=150.0,
        pitch_range_hz=50.0,
        intensity_mean_db=-18.0,
        pause_count=1,
        pause_total_s=0.5,
        pause_avg_s=0.5,
        filler_count=0,
        filler_per_minute=0.0,
    )
    rpt = TalkLabReport(
        recording_path="/tmp/x.wav",
        part_kind="bible_reading",
        language="es",
        duration_s=10.0,
        transcript=[],
        prosody=p,
        counsel_results=[],
        summary_top_3=[],
        summary_focus_3=[],
    )
    dumped = rpt.model_dump()
    rehydrated = TalkLabReport.model_validate(dumped)
    assert rehydrated.language == "es"
