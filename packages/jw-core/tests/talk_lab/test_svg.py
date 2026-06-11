"""SVG export tests (Fase 68 post-MVP)."""

from __future__ import annotations

from typing import Any

from jw_core.talk_lab.models import (
    CounselPointResult,
    ProsodyFeatures,
    TalkLabReport,
)
from jw_core.talk_lab.svg import report_to_svg


def _cp(point_id: str, score: int, **kw: Any) -> CounselPointResult:
    base = {
        "point_id": point_id,
        "title": point_id,
        "title_localized": point_id,
        "score": score,
    }
    base.update(kw)
    return CounselPointResult(**base)  # type: ignore[arg-type]


def _report(**kw: Any) -> TalkLabReport:
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
        counsel_results=kw.get(
            "counsel_results",
            [_cp("a", 3), _cp("b", 0), _cp("c", 2)],
        ),
        summary_top_3=kw.get("summary_top_3", ["a"]),
        summary_focus_3=kw.get("summary_focus_3", ["b"]),
    )


def test_svg_starts_with_svg_tag() -> None:
    out = report_to_svg(_report())
    assert out.startswith("<svg")
    assert out.endswith("</svg>")
    assert 'xmlns="http://www.w3.org/2000/svg"' in out


def test_svg_includes_header_with_meta() -> None:
    out = report_to_svg(_report())
    assert "bible_reading" in out
    assert "duration=60.0s" in out
    assert "130 wpm" in out


def test_svg_excludes_non_applicable_counsel_results() -> None:
    report = _report(
        counsel_results=[
            _cp("a", 3),
            _cp("skip", 2, applies=False),
            _cp("c", 0),
        ]
    )
    out = report_to_svg(report)
    # The non-applicable label should not appear as a bar label
    assert ">skip<" not in out


def test_svg_xml_escapes_quotes_and_brackets() -> None:
    report = _report(
        counsel_results=[
            _cp(
                "a",
                2,
                title_localized='Quote "x" & <bad>',
                suggestion='try "this" & fix',
            )
        ],
        summary_top_3=["a"],
        summary_focus_3=[],
    )
    out = report_to_svg(report)
    # No raw special chars should be in the SVG body
    assert '"x"' not in out
    assert "&quot;" in out or "Quote x" in out
    assert "&lt;bad&gt;" in out


def test_svg_includes_top_and_focus_summary() -> None:
    out = report_to_svg(_report())
    assert "Top 3:" in out
    assert "Focus 3:" in out
