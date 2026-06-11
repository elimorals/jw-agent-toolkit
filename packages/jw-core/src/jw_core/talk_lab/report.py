"""Report builder for talk_lab."""

from __future__ import annotations

from jw_core.talk_lab.models import (
    CounselPointResult,
    PartKind,
    ProsodyFeatures,
    TalkLabReport,
    TranscriptSegment,
)


def pick_top_focus(
    results: list[CounselPointResult],
) -> tuple[list[str], list[str]]:
    """Return (top_3, focus_3) lists of point_id strings.

    `top` collects high scorers (>=2) up to three.
    `focus` collects low scorers (<=1) up to three.
    Results with `applies=False` are skipped entirely.
    """

    eligible = [r for r in results if r.applies]
    by_score_desc = sorted(eligible, key=lambda r: r.score, reverse=True)
    top = [r.point_id for r in by_score_desc[:3] if r.score >= 2]
    by_score_asc = sorted(eligible, key=lambda r: r.score)
    focus = [r.point_id for r in by_score_asc[:3] if r.score <= 1]
    return top, focus


def build_report(
    *,
    recording_path: str,
    part_kind: PartKind,
    language: str,
    transcript: list[TranscriptSegment],
    prosody: ProsodyFeatures,
    counsel_results: list[CounselPointResult],
    trace_path: str | None = None,
) -> TalkLabReport:
    top, focus = pick_top_focus(counsel_results)
    return TalkLabReport(
        recording_path=recording_path,
        part_kind=part_kind,
        language=language,  # type: ignore[arg-type]
        duration_s=prosody.duration_s,
        transcript=transcript,
        prosody=prosody,
        counsel_results=counsel_results,
        summary_top_3=top,
        summary_focus_3=focus,
        trace_path=trace_path,
    )
