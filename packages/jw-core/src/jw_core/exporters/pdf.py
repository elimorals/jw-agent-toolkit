"""PDF exporter via WeasyPrint.

Renders the StudySheet through a Jinja2 template (theme) into HTML, then
WeasyPrint converts the HTML to PDF.

Themes available out of the box:
    - "plain"        — minimalist, sans-serif.
    - "study-sheet"  — serif notebook style.

User can override the template by dropping a file with the same name
under ~/.jw-agent-toolkit/templates/.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from jw_core.exporters.errors import ExportError, MissingDependencyError
from jw_core.exporters.ir import StudySheet
from jw_core.exporters.templates_resolver import render_html

Theme = Literal["plain", "study-sheet"]

_THEME_TO_TEMPLATE: dict[str, str] = {
    "plain": "plain.html.j2",
    "study-sheet": "study-sheet.html.j2",
}


def export_pdf(
    sheet: StudySheet,
    *,
    out: Path,
    theme: Theme = "study-sheet",
) -> Path:
    """Render `sheet` as PDF and write it to `out`. Returns `out`.

    Requires the [pdf] extra. Raises `MissingDependencyError` otherwise.
    """

    try:
        from weasyprint import HTML  # noqa: PLC0415  (lazy by design)
    except ImportError as exc:
        raise MissingDependencyError(
            "weasyprint is required for PDF export. Install with: pip install 'jw-core[pdf]'"
        ) from exc

    if theme not in _THEME_TO_TEMPLATE:
        raise ExportError(f"Unknown PDF theme {theme!r}. Available: {sorted(_THEME_TO_TEMPLATE)}")

    template_name = _THEME_TO_TEMPLATE[theme]
    html_body = render_html(sheet, template_name=template_name)

    out.parent.mkdir(parents=True, exist_ok=True)
    HTML(string=html_body).write_pdf(target=str(out))
    return out
