"""F31 PDF export wrapper for TalkLabReport (Fase 68 post-MVP).

Adapter: TalkLabReport -> jw_core.exporters.ir.StudySheet -> export_pdf.
Requires the `[pdf]` extra (weasyprint); raises on missing dependency.
"""

from __future__ import annotations

from pathlib import Path

from jw_core.exporters.ir import CitationIR, StudySection, StudySheet
from jw_core.exporters.pdf import export_pdf
from jw_core.talk_lab.models import TalkLabReport


def talklab_to_studysheet(report: TalkLabReport) -> StudySheet:
    """Convert a TalkLabReport into the F31 IR."""

    sections: list[StudySection] = []

    prosody_body = (
        f"- Duration: {report.duration_s:.1f}s\n"
        f"- Speech rate: {report.prosody.speech_rate_wpm:.0f} wpm\n"
        f"- Pauses: {report.prosody.pause_count} (total "
        f"{report.prosody.pause_total_s:.1f}s)\n"
        f"- Fillers: {report.prosody.filler_per_minute:.1f}/min"
    )
    sections.append(
        StudySection(
            heading="Prosody",
            body=prosody_body,
        )
    )

    for r in report.counsel_results:
        if not r.applies:
            continue
        body = (
            f"Score: {r.score}/3\n\n"
            + (r.suggestion or "(no suggestion)")
            + (
                "\n\nEvidence:\n- " + "\n- ".join(r.evidence)
                if r.evidence
                else ""
            )
        )
        sections.append(
            StudySection(
                heading=f"{r.point_id} {r.title_localized}",
                body=body,
            )
        )

    if report.summary_top_3:
        sections.append(
            StudySection(
                heading="Top 3 strengths",
                body="\n".join(f"- {p}" for p in report.summary_top_3),
            )
        )
    if report.summary_focus_3:
        sections.append(
            StudySection(
                heading="3 focus areas",
                body="\n".join(
                    f"- {p}" for p in report.summary_focus_3
                ),
            )
        )

    return StudySheet(
        title=f"TalkLab report — {report.part_kind}",
        subtitle=f"language={report.language}",
        language=report.language,
        sections=sections,
        footer_note=(
            "Local-first analysis; audio never leaves the disk."
        ),
        metadata={
            "duration_s": report.duration_s,
            "speech_rate_wpm": report.prosody.speech_rate_wpm,
        },
    )


def export_talk_lab_pdf(
    report: TalkLabReport, *, out: Path | str
) -> Path:
    """Render a `TalkLabReport` as PDF via F31. Raises on missing weasyprint."""

    sheet = talklab_to_studysheet(report)
    return export_pdf(sheet, out=Path(out))
