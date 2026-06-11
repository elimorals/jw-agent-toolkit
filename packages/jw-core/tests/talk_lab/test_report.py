"""Report builder tests."""

from __future__ import annotations

from typing import Any

from jw_core.talk_lab.models import (
    CounselPointResult,
    ProsodyFeatures,
    TalkLabReport,
)
from jw_core.talk_lab.report import build_report, pick_top_focus


def _cp(point_id: str, score: int, **kw: Any) -> CounselPointResult:
    return CounselPointResult(
        point_id=point_id,
        title=point_id,
        title_localized=point_id,
        score=score,  # type: ignore[arg-type]
        **kw,
    )


def test_pick_top_focus_picks_3_high_and_3_low() -> None:
    results = [
        _cp("a", 3),
        _cp("b", 3),
        _cp("c", 2),
        _cp("d", 1),
        _cp("e", 0),
        _cp("f", 1),
    ]
    top, focus = pick_top_focus(results)
    assert len(top) == 3
    assert len(focus) == 3
    assert "a" in top and "b" in top
    assert "e" in focus


def test_pick_top_focus_skips_non_applicable() -> None:
    results = [
        _cp("applies", 3),
        _cp("skip", 3, applies=False),
        _cp("low", 0),
    ]
    top, focus = pick_top_focus(results)
    assert "skip" not in top
    assert "applies" in top
    assert "low" in focus


def test_pick_top_focus_only_mid_scores_returns_empty() -> None:
    # All scores=2 -> nothing in focus (<=1)
    results = [_cp(f"x{i}", 2) for i in range(3)]
    top, focus = pick_top_focus(results)
    assert len(top) == 3
    assert focus == []


def test_build_report_smoke() -> None:
    prosody = ProsodyFeatures(
        duration_s=60.0,
        speech_rate_wpm=135.0,
        pitch_mean_hz=180.0,
        pitch_range_hz=80.0,
        intensity_mean_db=-20.0,
        pause_count=8,
        pause_total_s=12.0,
        pause_avg_s=1.5,
        filler_count=1,
        filler_per_minute=1.0,
    )
    rpt = build_report(
        recording_path="/tmp/x.wav",
        part_kind="bible_reading",
        language="es",
        transcript=[],
        prosody=prosody,
        counsel_results=[_cp("a", 3), _cp("b", 0)],
    )
    assert isinstance(rpt, TalkLabReport)
    assert rpt.duration_s == 60.0
    assert len(rpt.summary_top_3) == 1
    assert len(rpt.summary_focus_3) == 1
