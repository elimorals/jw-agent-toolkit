"""Markdown exporter.

Three citation styles:
  - inline-paren:  "...text (label, url)."
  - footnote:      "...text[^1]." with definitions at the end.
  - bibliography:  body without inline cites; numbered list at the end.

Pure-Python, no external dependencies. CommonMark-compatible output.
"""

from __future__ import annotations

import re
from pathlib import Path

from jw_core.exporters.ir import CitationIR, StudySection, StudySheet

CitationStyleStr = str  # 'inline-paren' | 'footnote' | 'bibliography'


def export_markdown(
    sheet: StudySheet,
    *,
    out: Path,
    citation_style: CitationStyleStr = "footnote",
) -> Path:
    """Render `sheet` as Markdown and write it to `out`. Returns `out`."""

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render_markdown(sheet, citation_style=citation_style), encoding="utf-8")
    return out


def render_markdown(
    sheet: StudySheet,
    *,
    citation_style: CitationStyleStr = "footnote",
) -> str:
    """Pure-string render of `sheet`. Easier to test than file I/O."""

    lines: list[str] = []
    lines.append(f"# {sheet.title}")
    if sheet.subtitle:
        lines.append(f"## {sheet.subtitle}")
    lines.append(f"_idioma: {sheet.language}_")
    lines.append("")

    # Collect global footnotes when citation_style == "footnote"
    footnote_defs: list[str] = []
    bibliography: list[CitationIR] = []
    counter = [0]

    for section in sheet.sections:
        lines.append(f"## {_escape_heading(section.heading)}")
        body = _escape_body(section.body)

        if citation_style == "inline-paren":
            body = _append_inline_citations(body, section.citations)
        elif citation_style == "footnote":
            body, fns = _attach_footnote_markers(body, section.citations, counter)
            footnote_defs.extend(fns)
        elif citation_style == "bibliography":
            bibliography.extend(section.citations)

        lines.append(body)

        if section.excerpt:
            lines.append("")
            for excerpt_line in section.excerpt.splitlines():
                lines.append(f"> {excerpt_line}")
        lines.append("")

    if citation_style == "footnote" and footnote_defs:
        lines.append("")
        lines.extend(footnote_defs)

    if citation_style == "bibliography" and bibliography:
        lines.append("")
        lines.append("## Fuentes")
        for i, cite in enumerate(bibliography, 1):
            lines.append(f"{i}. [{cite.short_label or cite.title or cite.url}]({cite.url})")

    if sheet.footer_note:
        lines.append("")
        lines.append("---")
        lines.append(f"_{sheet.footer_note}_")

    return "\n".join(lines).rstrip() + "\n"


# ── helpers ──


_DANGEROUS_MD = re.compile(r"([\[\]\(\)])")


def _escape_heading(text: str) -> str:
    """Headings only need # escaping; brackets etc. are usually fine but we strip newlines."""
    return text.replace("\n", " ").strip()


def _escape_body(text: str) -> str:
    """Escape brackets/parens to avoid accidental markdown link injection."""
    return _DANGEROUS_MD.sub(r"\\\1", text)


def _append_inline_citations(body: str, citations: list[CitationIR]) -> str:
    if not citations:
        return body
    parens = ", ".join(f"{c.short_label or c.title or 'fuente'}, {c.url}" for c in citations)
    if body.endswith("."):
        return f"{body[:-1]} ({parens})."
    return f"{body} ({parens})"


def _attach_footnote_markers(
    body: str,
    citations: list[CitationIR],
    counter: list[int],
) -> tuple[str, list[str]]:
    """Append [^N] markers to the body and return the footnote definitions."""

    if not citations:
        return body, []
    markers: list[str] = []
    defs: list[str] = []
    for cite in citations:
        counter[0] += 1
        n = counter[0]
        markers.append(f"[^{n}]")
        label = cite.short_label or cite.title or cite.url
        defs.append(f"[^{n}]: [{label}]({cite.url})")
    marker_str = "".join(markers)
    if body.endswith("."):
        body = body[:-1] + marker_str + "."
    else:
        body = body + marker_str
    return body, defs
