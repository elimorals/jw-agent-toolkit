"""SVG visualization of a DoctrinalDrift timeline (Fase 72 post-MVP).

Renders eras as colored squares on a horizontal axis. Drift arrows
connect consecutive populated eras with width proportional to
`cosine_delta` and color by significance (green minor, orange
moderate, red major). The explanatory note Prov 4:18 is rendered at
the bottom verbatim (truncated to fit).
"""

from __future__ import annotations

from jw_core.drift.models import ALL_ERAS, DoctrinalDrift, Significance

_WIDTH = 900
_HEIGHT = 320
_ERA_Y = 130
_ERA_SIZE = 40
_LEFT_PAD = 60
_RIGHT_PAD = 60

_SIG_COLOR: dict[Significance, str] = {
    "minor": "#27ae60",
    "moderate": "#e67e22",
    "major": "#c0392b",
}


def _xml_escape(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _era_x(idx: int) -> int:
    n = len(ALL_ERAS)
    span = _WIDTH - _LEFT_PAD - _RIGHT_PAD
    if n == 1:
        return _LEFT_PAD + span // 2
    return _LEFT_PAD + int(idx * span / (n - 1))


def drift_to_svg(report: DoctrinalDrift) -> str:
    """Render a `DoctrinalDrift` report as a self-contained SVG string."""

    populated = {s.era for s in report.era_snapshots}
    parts: list[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{_WIDTH}" '
        f'height="{_HEIGHT}" viewBox="0 0 {_WIDTH} {_HEIGHT}" '
        f'font-family="system-ui,sans-serif">',
        f'  <rect width="{_WIDTH}" height="{_HEIGHT}" fill="#fafafa"/>',
        f'  <text x="20" y="30" font-size="18" font-weight="700" fill="#222">'
        f"Doctrinal drift: {_xml_escape(report.query)}</text>",
        f'  <text x="20" y="52" font-size="12" fill="#555">'
        f"language={_xml_escape(report.language)} · events="
        f"{len(report.drift_events)} · "
        f"insufficient_data={'yes' if report.insufficient_data else 'no'}"
        f"</text>",
    ]

    # Era track
    parts.append(
        f'  <line x1="{_LEFT_PAD - 10}" y1="{_ERA_Y + _ERA_SIZE // 2}" '
        f'x2="{_WIDTH - _RIGHT_PAD + 10}" y2="{_ERA_Y + _ERA_SIZE // 2}" '
        f'stroke="#bbb" stroke-width="2"/>'
    )

    # Era markers
    for i, era in enumerate(ALL_ERAS):
        x = _era_x(i)
        fill = "#3498db" if era in populated else "#ecf0f1"
        stroke = "#2c3e50" if era in populated else "#bdc3c7"
        parts.append(
            f'  <rect x="{x - _ERA_SIZE // 2}" y="{_ERA_Y}" '
            f'width="{_ERA_SIZE}" height="{_ERA_SIZE}" rx="6" ry="6" '
            f'fill="{fill}" stroke="{stroke}" stroke-width="1.5"/>'
        )
        parts.append(
            f'  <text x="{x}" y="{_ERA_Y + _ERA_SIZE + 18}" '
            f'font-size="11" text-anchor="middle" fill="#555">{era}</text>'
        )

    # Drift event arrows
    era_to_idx = {era: i for i, era in enumerate(ALL_ERAS)}
    for ev in report.drift_events:
        i_from = era_to_idx.get(ev.from_era)
        i_to = era_to_idx.get(ev.to_era)
        if i_from is None or i_to is None:
            continue
        x1 = _era_x(i_from) + _ERA_SIZE // 2
        x2 = _era_x(i_to) - _ERA_SIZE // 2
        y_arrow = _ERA_Y - 18
        color = _SIG_COLOR.get(ev.significance, "#888")
        width = max(2.0, min(8.0, ev.cosine_delta * 30))
        parts.append(
            f'  <path d="M{x1} {_ERA_Y + _ERA_SIZE // 2} '
            f"Q{(x1 + x2) // 2} {y_arrow} {x2} {_ERA_Y + _ERA_SIZE // 2}\" "
            f'stroke="{color}" stroke-width="{width:.1f}" fill="none"/>'
        )
        mid_x = (x1 + x2) // 2
        parts.append(
            f'  <text x="{mid_x}" y="{y_arrow - 4}" font-size="10" '
            f'text-anchor="middle" fill="{color}">'
            f"Δ={ev.cosine_delta:.2f} · {ev.significance}</text>"
        )

    # Legend (significance bands)
    legend_y = 230
    legend_items = ("minor", "moderate", "major")
    for j, sig in enumerate(legend_items):
        x = 20 + j * 130
        color = _SIG_COLOR[sig]  # type: ignore[index]
        parts.append(
            f'  <rect x="{x}" y="{legend_y}" width="14" height="14" '
            f'fill="{color}" rx="2" ry="2"/>'
        )
        parts.append(
            f'  <text x="{x + 20}" y="{legend_y + 12}" font-size="11" '
            f'fill="#444">{sig}</text>'
        )

    # Explanatory note (truncated)
    note = _xml_escape(report.explanatory_note.replace("\n", " "))[:280]
    parts.append(
        f'  <text x="20" y="{_HEIGHT - 30}" font-size="10" fill="#666">'
        f"{note}</text>"
    )

    parts.append("</svg>")
    return "\n".join(parts)
