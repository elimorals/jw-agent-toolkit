"""SVG visualization of a TalkLabReport timeline (Fase 68 post-MVP).

Single-file SVG. No JS, no external CSS, no dependencies beyond
Pydantic. The output is a 800×N pixel canvas with one bar per counsel
result colored by score (red 0 → green 3) and a small prosody footer.
"""

from __future__ import annotations

from jw_core.talk_lab.models import CounselPointResult, TalkLabReport

_SCORE_COLORS: dict[int, str] = {
    0: "#c0392b",  # red
    1: "#e67e22",  # orange
    2: "#f1c40f",  # yellow
    3: "#27ae60",  # green
}

_BAR_HEIGHT = 28
_BAR_GAP = 6
_LEFT_PAD = 220
_RIGHT_PAD = 40
_TOP_PAD = 80
_BAR_MAX_WIDTH = 480
_WIDTH = 800


def _xml_escape(text: str) -> str:
    """Minimal XML escape for SVG text nodes."""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _bar(
    *,
    y: int,
    label: str,
    score: int,
    suggestion: str,
) -> str:
    width = int((score / 3.0) * _BAR_MAX_WIDTH) if score > 0 else 8
    fill = _SCORE_COLORS.get(score, "#888")
    label_safe = _xml_escape(label[:30])
    suggestion_safe = _xml_escape(suggestion[:90])
    return (
        f'  <g transform="translate(0,{y})">'
        f'<text x="10" y="{_BAR_HEIGHT - 8}" '
        f'font-size="13" fill="#333">{label_safe}</text>'
        f'<rect x="{_LEFT_PAD}" y="2" width="{width}" '
        f'height="{_BAR_HEIGHT - 4}" rx="3" ry="3" fill="{fill}"/>'
        f'<text x="{_LEFT_PAD + width + 8}" y="{_BAR_HEIGHT - 8}" '
        f'font-size="11" fill="#666">{score}/3</text>'
        f'<title>{suggestion_safe}</title>'
        f"</g>"
    )


def report_to_svg(report: TalkLabReport) -> str:
    """Render a `TalkLabReport` as a self-contained SVG string."""

    applicable = [r for r in report.counsel_results if r.applies]
    n = len(applicable)
    height = _TOP_PAD + n * (_BAR_HEIGHT + _BAR_GAP) + 120

    parts: list[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{_WIDTH}" '
        f'height="{height}" viewBox="0 0 {_WIDTH} {height}" '
        f'font-family="system-ui,sans-serif">',
        f'  <rect width="{_WIDTH}" height="{height}" fill="#fafafa"/>',
        f'  <text x="20" y="30" font-size="18" font-weight="700" '
        f'fill="#222">TalkLab report ({_xml_escape(report.part_kind)})</text>',
        f'  <text x="20" y="52" font-size="12" fill="#555">'
        f"language={_xml_escape(report.language)} · "
        f"duration={report.duration_s:.1f}s · "
        f"rate={report.prosody.speech_rate_wpm:.0f} wpm · "
        f"fillers={report.prosody.filler_per_minute:.1f}/min"
        f"</text>",
    ]

    y = _TOP_PAD
    for r in applicable:
        parts.append(
            _bar(
                y=y,
                label=r.title_localized or r.title,
                score=int(r.score),
                suggestion=r.suggestion,
            )
        )
        y += _BAR_HEIGHT + _BAR_GAP

    if report.summary_top_3:
        parts.append(
            f'  <text x="20" y="{y + 30}" font-size="12" fill="#27ae60">'
            f'Top 3: {_xml_escape(", ".join(report.summary_top_3))}</text>'
        )
    if report.summary_focus_3:
        parts.append(
            f'  <text x="20" y="{y + 50}" font-size="12" fill="#c0392b">'
            f'Focus 3: {_xml_escape(", ".join(report.summary_focus_3))}</text>'
        )

    parts.append("</svg>")
    return "\n".join(parts)
