"""F31 PDF wrapper tests (Fase 68 post-MVP)."""

from __future__ import annotations

from typing import Any

import pytest

from jw_core.talk_lab.models import (
    CounselPointResult,
    ProsodyFeatures,
    TalkLabReport,
)
from jw_core.talk_lab.pdf_export import (
    export_talk_lab_pdf,
    talklab_to_studysheet,
)


def _cp(point_id: str, score: int, **kw: Any) -> CounselPointResult:
    base = {
        "point_id": point_id,
        "title": point_id,
        "title_localized": point_id,
        "score": score,
    }
    base.update(kw)
    return CounselPointResult(**base)  # type: ignore[arg-type]


def _report() -> TalkLabReport:
    prosody = ProsodyFeatures(
        duration_s=60.0,
        speech_rate_wpm=130.0,
        pitch_mean_hz=180.0,
        pitch_range_hz=80.0,
        intensity_mean_db=-20.0,
        pause_count=10,
        pause_total_s=12.0,
        pause_avg_s=1.2,
        filler_count=2,
        filler_per_minute=2.0,
    )
    return TalkLabReport(
        recording_path="/tmp/x.wav",
        part_kind="bible_reading",
        language="es",
        duration_s=60.0,
        transcript=[],
        prosody=prosody,
        counsel_results=[
            _cp("a", 3, suggestion="great"),
            _cp("b", 0, suggestion="needs work"),
            _cp("skip", 2, applies=False),
        ],
        summary_top_3=["a"],
        summary_focus_3=["b"],
    )


def test_studysheet_round_trip_has_expected_sections() -> None:
    sheet = talklab_to_studysheet(_report())
    headings = [s.heading for s in sheet.sections]
    assert "Prosody" in headings
    assert "a a" in headings or "a a" in str(headings)  # cp-id + title_localized
    # Non-applicable result is skipped
    assert all("skip skip" not in h for h in headings)
    assert "Top 3 strengths" in headings
    assert "3 focus areas" in headings


def test_studysheet_title_contains_part_kind() -> None:
    sheet = talklab_to_studysheet(_report())
    assert "bible_reading" in sheet.title


def test_studysheet_metadata_carries_duration() -> None:
    sheet = talklab_to_studysheet(_report())
    assert sheet.metadata["duration_s"] == 60.0


def test_export_pdf_raises_clear_error_when_weasy_missing(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    """Without weasyprint installed, F31 raises MissingDependencyError."""

    import sys

    monkeypatch.setitem(sys.modules, "weasyprint", None)
    out = tmp_path / "x.pdf"
    with pytest.raises(Exception):  # MissingDependencyError or ImportError
        export_talk_lab_pdf(_report(), out=out)
