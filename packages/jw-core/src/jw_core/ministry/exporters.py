"""Serializers for :class:`MonthlyReport` → markdown / csv / pdf.

PDF is optional and gated by the ``[pdf]`` extra (weasyprint + jinja2).
The other two exporters are stdlib-only.
"""

from __future__ import annotations

import csv
import io
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from jw_core.ministry.field_report import MonthlyReport


_TAG_LABELS_ES = {
    "street": "Predicación pública",
    "return_visit": "Revisitas (horas)",
    "bible_study": "Estudios bíblicos (horas)",
    "online": "En línea",
    "phone": "Teléfono",
    "cart": "Testimonio con exhibidor",
    "letter": "Cartas",
    "other": "Otro",
    "untagged": "Sin clasificar",
}


def _tag_label(tag: str) -> str:
    return _TAG_LABELS_ES.get(tag, tag)


def render_markdown(report: "MonthlyReport") -> str:
    """Render a human-friendly markdown report (in Spanish)."""

    lines: list[str] = []
    lines.append(f"# Informe mensual — {report.month}")
    lines.append("")
    lines.append("## Resumen")
    lines.append("")
    lines.append(f"- **Horas totales**: {report.total_hours_display} ({report.total_hours:.2f} h)")
    lines.append(f"- **Días con servicio**: {report.days_with_service}")
    lines.append(f"- **Cursos bíblicos activos (máximo)**: {report.active_studies_max}")
    lines.append(f"- **Revisitas registradas**: {report.revisits_count}")
    lines.append(f"- **Entradas registradas**: {report.entries_count}")
    lines.append("")
    if report.breakdown_by_tag:
        lines.append("## Desglose por modalidad")
        lines.append("")
        lines.append("| Modalidad | Tag | Horas |")
        lines.append("|---|---|---:|")
        for tag in sorted(report.breakdown_by_tag, key=lambda t: -report.breakdown_by_tag[t]):
            lines.append(
                f"| {_tag_label(tag)} | `{tag}` | {report.breakdown_by_tag[tag]:.2f} |"
            )
        lines.append("")
    lines.append("---")
    lines.append("")
    lines.append(
        "_Cursos bíblicos activos se reportan como el **máximo** durante "
        "el mes (práctica JW vigente). Las revisitas vienen del store "
        "local de RevisitTracker (Fase 12, solo lectura)._"
    )
    return "\n".join(lines)


def render_csv(report: "MonthlyReport") -> str:
    """Render the report as a long-form CSV (mes, metrica, valor)."""

    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(["mes", "metrica", "valor"])
    w.writerow([report.month, "horas_totales", f"{report.total_hours:.2f}"])
    w.writerow([report.month, "horas_display", report.total_hours_display])
    w.writerow([report.month, "dias_con_servicio", str(report.days_with_service)])
    w.writerow([report.month, "cursos_activos_max", str(report.active_studies_max)])
    w.writerow([report.month, "revisitas", str(report.revisits_count)])
    w.writerow([report.month, "entradas_registradas", str(report.entries_count)])
    for tag, hours in sorted(report.breakdown_by_tag.items()):
        w.writerow([report.month, f"tag.{tag}", f"{hours:.2f}"])
    return buf.getvalue()
