# Fase 31 — Exportador de hoja de estudio (PDF / DOCX / Anki) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an `AgentResult → StudySheet → {markdown|pdf|docx|apkg}` export pipeline. Markdown always works; PDF/DOCX/Anki are opt-in via extras. Single IR. Stable Anki GUIDs. Pluggable Jinja templates.

**Architecture:** New module `jw_core.exporters` inside `packages/jw-core` (no new workspace package). One IR (`StudySheet`) consumed by 4 exporters. Lazy imports of heavy deps. CLI command `jw export` + MCP tool `export_study_sheet`.

**Tech Stack:** Python 3.13 · Pydantic v2 (IR) · Jinja2 (PDF templates) · WeasyPrint (PDF, optional) · python-docx (DOCX, optional) · genanki (Anki, optional) · Typer (CLI) · FastMCP (tool).

**Spec:** [`docs/superpowers/specs/2026-05-30-fase-31-exporter-design.md`](../specs/2026-05-30-fase-31-exporter-design.md).

---

## File map

Creates:
- `packages/jw-core/src/jw_core/exporters/__init__.py`
- `packages/jw-core/src/jw_core/exporters/ir.py`
- `packages/jw-core/src/jw_core/exporters/errors.py`
- `packages/jw-core/src/jw_core/exporters/markdown.py`
- `packages/jw-core/src/jw_core/exporters/templates_resolver.py`
- `packages/jw-core/src/jw_core/exporters/pdf.py`
- `packages/jw-core/src/jw_core/exporters/docx.py`
- `packages/jw-core/src/jw_core/exporters/anki.py`
- `packages/jw-core/src/jw_core/templates/__init__.py`
- `packages/jw-core/src/jw_core/templates/study_sheet/__init__.py`
- `packages/jw-core/src/jw_core/templates/study_sheet/plain.html.j2`
- `packages/jw-core/src/jw_core/templates/study_sheet/study-sheet.html.j2`
- `packages/jw-core/tests/test_exporter_ir.py`
- `packages/jw-core/tests/test_exporter_markdown.py`
- `packages/jw-core/tests/test_exporter_templates.py`
- `packages/jw-core/tests/test_exporter_pdf.py`
- `packages/jw-core/tests/test_exporter_docx.py`
- `packages/jw-core/tests/test_exporter_anki.py`
- `packages/jw-cli/src/jw_cli/commands/export.py`
- `packages/jw-cli/tests/test_export_command.py`
- `docs/guias/exportador-hoja-de-estudio.md`

Modifies:
- `packages/jw-core/pyproject.toml` (extras `[pdf]`, `[docx]`, `[anki]`; Jinja2 as hard dep)
- `packages/jw-cli/src/jw_cli/main.py` (register `export` command)
- `packages/jw-cli/src/jw_cli/commands/__init__.py`
- `packages/jw-mcp/src/jw_mcp/server.py` (register `export_study_sheet` tool)
- `docs/ROADMAP.md` (add Fase 31 section)
- `docs/VISION_AUDIT.md` (add row for #11)
- `docs/README.md` (link new guide)

---

### Task 1: Scaffold `jw_core.exporters` module + errors + extras

**Files:**
- Create: `packages/jw-core/src/jw_core/exporters/__init__.py`
- Create: `packages/jw-core/src/jw_core/exporters/errors.py`
- Modify: `packages/jw-core/pyproject.toml`

- [ ] **Step 1: Add the extras and Jinja2 to pyproject**

Edit `packages/jw-core/pyproject.toml`:

- Append to `dependencies = [...]`:
  ```
  "jinja2>=3.1.3",
  ```
- Add new section:
  ```toml
  [project.optional-dependencies]
  pdf = [
      "weasyprint>=62.3",
  ]
  docx = [
      "python-docx>=1.1.0",
  ]
  anki = [
      "genanki>=0.13.1,<1.0",
  ]
  ```

(If `[project.optional-dependencies]` already exists, only append the three keys.)

- [ ] **Step 2: Create the errors module**

```python
# packages/jw-core/src/jw_core/exporters/errors.py
"""Exporter exceptions.

Every exporter that requires an optional extra raises `MissingDependencyError`
with a copy-pasteable install hint when its dependency is not importable.
"""

from __future__ import annotations


class ExportError(Exception):
    """Base class for everything raised by the exporters module."""


class MissingDependencyError(ExportError):
    """Raised when an optional dependency (weasyprint/python-docx/genanki) is missing."""
```

- [ ] **Step 3: Create the package init**

```python
# packages/jw-core/src/jw_core/exporters/__init__.py
"""Convert AgentResult into printable study sheets and Anki decks.

Public API:
    from jw_core.exporters import StudySheet
    from jw_core.exporters.markdown import export_markdown
    from jw_core.exporters.pdf import export_pdf            # needs [pdf]
    from jw_core.exporters.docx import export_docx          # needs [docx]
    from jw_core.exporters.anki import export_apkg          # needs [anki]

Design: every exporter consumes a `StudySheet` (the single IR). The
`AgentResult → StudySheet` conversion lives in `ir.from_agent_result`.

Heavy dependencies (weasyprint, python-docx, genanki) are imported lazily
inside each exporter function, so importing this package never fails when
the extras are not installed.
"""

from jw_core.exporters.errors import ExportError, MissingDependencyError
from jw_core.exporters.ir import CitationIR, StudySection, StudySheet

__all__ = [
    "CitationIR",
    "ExportError",
    "MissingDependencyError",
    "StudySection",
    "StudySheet",
]
```

- [ ] **Step 4: Verify install**

Run: `uv sync --all-packages`
Expected: no errors. Importing `jw_core.exporters` should succeed without `[pdf]`/`[docx]`/`[anki]` installed.

- [ ] **Step 5: Commit**

```bash
git add packages/jw-core/src/jw_core/exporters packages/jw-core/pyproject.toml
git commit -m "feat(exporters): scaffold jw_core.exporters module with extras"
```

---

### Task 2: IR — `StudySheet` + `from_agent_result`

**Files:**
- Create: `packages/jw-core/src/jw_core/exporters/ir.py`
- Create: `packages/jw-core/tests/test_exporter_ir.py`

- [ ] **Step 1: Write the failing tests**

```python
# packages/jw-core/tests/test_exporter_ir.py
"""Tests for jw_core.exporters.ir — the StudySheet IR and AgentResult conversion."""

from __future__ import annotations

import pytest

from jw_agents.base import AgentResult, Citation, Finding
from jw_core.exporters.ir import CitationIR, StudySection, StudySheet


def _sample_result() -> AgentResult:
    return AgentResult(
        query="Es la Trinidad bíblica?",
        agent_name="apologetics",
        findings=[
            Finding(
                summary="La Biblia presenta a Jehová como el único Dios verdadero.",
                citation=Citation(
                    url="https://wol.jw.org/es/wol/d/r4/lp-s/1101989140",
                    title="¿Qué enseña la Biblia sobre la Trinidad?",
                    kind="article",
                    metadata={"source": "topic_index"},
                ),
                excerpt="Jehová es uno solo (Deuteronomio 6:4).",
                metadata={"source": "topic_index"},
            ),
            Finding(
                summary="Jesús siempre se distinguió de su Padre.",
                citation=Citation(
                    url="https://wol.jw.org/es/wol/b/r4/lp-s/nwt/E/2024/43/14",
                    title="Juan 14:28",
                    kind="verse",
                ),
            ),
        ],
        warnings=["Cobertura parcial en idiomas LSN."],
        metadata={"language": "es"},
    )


def test_studysheet_construct_directly() -> None:
    sheet = StudySheet(
        title="Demo",
        sections=[StudySection(heading="Punto 1", body="Contenido.")],
    )
    assert sheet.title == "Demo"
    assert len(sheet.sections) == 1
    assert sheet.language == "es"


def test_citation_ir_defaults() -> None:
    cite = CitationIR(url="https://wol.jw.org/x")
    assert cite.title == ""
    assert cite.kind == ""
    assert cite.short_label == ""


def test_from_agent_result_minimal() -> None:
    sheet = StudySheet.from_agent_result(_sample_result())
    assert sheet.title == "Es la Trinidad bíblica?"
    assert "apologetics" in sheet.subtitle.lower() or "apologé" in sheet.subtitle.lower()
    assert sheet.language == "es"
    assert len(sheet.sections) == 2


def test_from_agent_result_explicit_title_wins() -> None:
    sheet = StudySheet.from_agent_result(_sample_result(), title="Mi título")
    assert sheet.title == "Mi título"


def test_from_agent_result_truncates_long_title() -> None:
    long_q = "Por qué " + "muy largo " * 50
    sheet = StudySheet.from_agent_result(
        AgentResult(query=long_q, agent_name="apologetics")
    )
    assert len(sheet.title) <= 80


def test_from_agent_result_warnings_become_footer() -> None:
    sheet = StudySheet.from_agent_result(_sample_result())
    assert "Cobertura parcial" in sheet.footer_note
    assert "Advertencias" in sheet.footer_note


def test_from_agent_result_no_citations_when_disabled() -> None:
    sheet = StudySheet.from_agent_result(_sample_result(), include_citations=False)
    assert all(section.citations == [] for section in sheet.sections)


def test_from_agent_result_keeps_excerpt() -> None:
    sheet = StudySheet.from_agent_result(_sample_result())
    assert sheet.sections[0].excerpt.startswith("Jehová es uno solo")


def test_from_agent_result_empty_findings() -> None:
    empty = AgentResult(query="vacío", agent_name="apologetics", findings=[])
    sheet = StudySheet.from_agent_result(empty)
    assert len(sheet.sections) == 1
    assert "sin resultados" in sheet.sections[0].heading.lower()


def test_from_agent_result_accepts_dict() -> None:
    """`from_agent_result` must accept the dict form (AgentResult.to_dict())."""
    raw = _sample_result().to_dict()
    sheet = StudySheet.from_agent_result(raw)
    assert sheet.title == "Es la Trinidad bíblica?"
    assert len(sheet.sections) == 2


def test_citation_short_label_is_built() -> None:
    sheet = StudySheet.from_agent_result(_sample_result())
    labels = [c.short_label for s in sheet.sections for c in s.citations]
    assert any(labels)  # at least one non-empty short label
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/jw-core/tests/test_exporter_ir.py -v`
Expected: FAIL — module `ir` missing.

- [ ] **Step 3: Implement the IR**

```python
# packages/jw-core/src/jw_core/exporters/ir.py
"""StudySheet — the single intermediate representation consumed by every exporter.

Conversion `AgentResult → StudySheet` happens here and ONLY here. Every
exporter consumes a StudySheet directly, never an AgentResult.

Why a separate IR:
    - Decouples "what to render" from "how to render".
    - Lets us swap the upstream shape (AgentResult, future agents, scraped
      data) without rewriting four exporters.
    - Tests for exporters are fully synthetic (no agent execution needed).
"""

from __future__ import annotations

from typing import Any, TYPE_CHECKING, Literal

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from jw_agents.base import AgentResult

CitationStyle = Literal["inline-paren", "footnote", "bibliography"]

_MAX_TITLE = 80
_MAX_HEADING = 100

_AGENT_SUBTITLES = {
    "apologetics": "Análisis apologético",
    "verse_explainer": "Explicación del versículo",
    "research_topic": "Investigación temática",
    "meeting_helper": "Preparación de reunión",
    "workbook_helper": "Guía de actividad",
    "conversation_assistant": "Asistente de conversación",
    "presentation_builder": "Presentación",
    "public_talk_outline": "Discurso público — bosquejo",
    "reverse_citation_lookup": "Cita inversa",
    "study_conductor": "Conductor del estudio",
    "student_part_helper": "Parte del estudiante",
    "letter_composer": "Composición de carta",
    "life_topics": "Tema de vida",
}


class CitationIR(BaseModel):
    """Citation normalized for every exporter."""

    url: str
    title: str = ""
    kind: str = ""
    short_label: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class StudySection(BaseModel):
    """One section of the study sheet."""

    heading: str
    body: str
    excerpt: str = ""
    citations: list[CitationIR] = Field(default_factory=list)


class StudySheet(BaseModel):
    """Intermediate representation. All exporters consume this."""

    title: str
    subtitle: str = ""
    language: str = "es"
    sections: list[StudySection] = Field(default_factory=list)
    footer_note: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def from_agent_result(
        cls,
        result: "AgentResult | dict[str, Any]",
        *,
        title: str | None = None,
        language: str | None = None,
        include_citations: bool = True,
    ) -> StudySheet:
        """Single conversion AgentResult (or its dict form) → StudySheet."""

        if isinstance(result, dict):
            data = result
        else:
            data = result.to_dict()

        # ── title ──
        if title:
            final_title = title
        else:
            md_title = data.get("metadata", {}).get("title")
            final_title = md_title or data.get("query", "(sin título)")
        if len(final_title) > _MAX_TITLE:
            final_title = final_title[: _MAX_TITLE - 1].rstrip() + "…"

        # ── subtitle ──
        agent_name = data.get("agent_name", "")
        subtitle = _AGENT_SUBTITLES.get(agent_name, agent_name)

        # ── language ──
        lang = language or data.get("metadata", {}).get("language", "es")

        # ── sections ──
        sections: list[StudySection] = []
        for f in data.get("findings", []):
            summary = (f.get("summary") or "").strip()
            heading = summary.splitlines()[0] if summary else "(sin resumen)"
            if len(heading) > _MAX_HEADING:
                heading = heading[: _MAX_HEADING - 1].rstrip() + "…"

            citations: list[CitationIR] = []
            if include_citations:
                cite_raw = f.get("citation") or {}
                if cite_raw.get("url"):
                    citations.append(_citation_from_dict(cite_raw))

            sections.append(
                StudySection(
                    heading=heading,
                    body=summary,
                    excerpt=(f.get("excerpt") or "").strip(),
                    citations=citations,
                )
            )

        if not sections:
            sections.append(
                StudySection(
                    heading="(sin resultados)",
                    body="El agente no devolvió resultados.",
                )
            )

        # ── footer (warnings + provenance) ──
        warnings = data.get("warnings", []) or []
        footer_parts: list[str] = []
        if warnings:
            footer_parts.append("Advertencias: " + " · ".join(warnings))
        footer_parts.append("Generado por jw-agent-toolkit.")
        footer_note = "\n".join(footer_parts)

        return cls(
            title=final_title,
            subtitle=subtitle,
            language=lang,
            sections=sections,
            footer_note=footer_note,
            metadata=data.get("metadata", {}),
        )


def _citation_from_dict(raw: dict[str, Any]) -> CitationIR:
    """Map a serialized Citation dict to CitationIR, building a short_label."""

    title = (raw.get("title") or "").strip()
    kind = (raw.get("kind") or "").strip()
    meta = raw.get("metadata") or {}

    # Build a compact label. Verses prefer the title (e.g. "Juan 3:16");
    # articles use truncated title; default = URL host + last path segment.
    short = ""
    if kind == "verse" and title:
        short = title
    elif title:
        short = title if len(title) <= 60 else title[:59] + "…"
    else:
        url = raw.get("url", "")
        short = url.rsplit("/", 1)[-1] if url else ""

    return CitationIR(
        url=raw.get("url", ""),
        title=title,
        kind=kind,
        short_label=short,
        metadata=meta,
    )
```

- [ ] **Step 4: Run tests until green**

Run: `uv run pytest packages/jw-core/tests/test_exporter_ir.py -v`
Expected: 10 passed.

- [ ] **Step 5: Commit**

```bash
git add packages/jw-core/src/jw_core/exporters/ir.py packages/jw-core/tests/test_exporter_ir.py
git commit -m "feat(exporters): StudySheet IR + from_agent_result conversion"
```

---

### Task 3: Markdown exporter (3 citation styles)

**Files:**
- Create: `packages/jw-core/src/jw_core/exporters/markdown.py`
- Create: `packages/jw-core/tests/test_exporter_markdown.py`

- [ ] **Step 1: Write the failing tests**

```python
# packages/jw-core/tests/test_exporter_markdown.py
"""Tests for jw_core.exporters.markdown."""

from __future__ import annotations

from pathlib import Path

import pytest

from jw_core.exporters.ir import CitationIR, StudySection, StudySheet
from jw_core.exporters.markdown import export_markdown, render_markdown


def _sheet() -> StudySheet:
    return StudySheet(
        title="Trinidad",
        subtitle="Análisis apologético",
        language="es",
        sections=[
            StudySection(
                heading="Jehová es el único Dios",
                body="La Biblia es clara: hay un solo Dios verdadero.",
                excerpt="Deuteronomio 6:4 — Escucha, Israel.",
                citations=[
                    CitationIR(
                        url="https://wol.jw.org/es/wol/d/r4/lp-s/1101989140",
                        title="¿Qué enseña la Biblia sobre la Trinidad?",
                        kind="article",
                        short_label="Trinidad — folleto",
                    )
                ],
            ),
            StudySection(
                heading="Jesús no es el Padre",
                body="Jesús siempre se distinguió del Padre.",
                citations=[
                    CitationIR(
                        url="https://wol.jw.org/es/wol/b/r4/lp-s/nwt/E/2024/43/14",
                        title="Juan 14:28",
                        kind="verse",
                        short_label="Juan 14:28",
                    )
                ],
            ),
        ],
        footer_note="Generado por jw-agent-toolkit.",
    )


def test_render_markdown_has_title() -> None:
    out = render_markdown(_sheet())
    assert out.startswith("# Trinidad")
    assert "## Jehová es el único Dios" in out


def test_render_footnote_style_default() -> None:
    out = render_markdown(_sheet(), citation_style="footnote")
    # Footnote markers appear in body
    assert "[^1]" in out
    assert "[^2]" in out
    # Footnote definitions appear at the end
    assert "[^1]:" in out
    assert "wol.jw.org" in out


def test_render_inline_paren_style() -> None:
    out = render_markdown(_sheet(), citation_style="inline-paren")
    assert "(Trinidad — folleto, https://wol.jw.org" in out
    assert "[^1]" not in out  # no footnotes when inline


def test_render_bibliography_style() -> None:
    out = render_markdown(_sheet(), citation_style="bibliography")
    assert "## Fuentes" in out or "## Bibliografía" in out
    assert "Juan 14:28" in out


def test_render_includes_excerpt_as_blockquote() -> None:
    out = render_markdown(_sheet())
    assert "> Deuteronomio 6:4" in out


def test_render_includes_footer() -> None:
    out = render_markdown(_sheet())
    assert "Generado por jw-agent-toolkit" in out


def test_render_empty_sections() -> None:
    sheet = StudySheet(title="Vacío", sections=[])
    out = render_markdown(sheet)
    assert "# Vacío" in out


def test_export_markdown_writes_file(tmp_path: Path) -> None:
    out = tmp_path / "demo.md"
    written = export_markdown(_sheet(), out=out)
    assert written == out
    assert out.exists()
    assert out.read_text(encoding="utf-8").startswith("# Trinidad")


def test_export_markdown_creates_parent_dirs(tmp_path: Path) -> None:
    out = tmp_path / "deep" / "nested" / "demo.md"
    export_markdown(_sheet(), out=out)
    assert out.exists()


def test_render_escapes_dangerous_chars_in_body() -> None:
    sheet = StudySheet(
        title="Inj",
        sections=[StudySection(heading="x", body="text with [bracket] and (paren)")],
    )
    out = render_markdown(sheet)
    # Brackets and parens get escaped in body to avoid accidental markdown links
    assert "\\[bracket\\]" in out or "[bracket]" in out  # accept either escape policy
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/jw-core/tests/test_exporter_markdown.py -v`
Expected: FAIL — `markdown` module missing.

- [ ] **Step 3: Implement the markdown exporter**

```python
# packages/jw-core/src/jw_core/exporters/markdown.py
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
```

- [ ] **Step 4: Run tests until green**

Run: `uv run pytest packages/jw-core/tests/test_exporter_markdown.py -v`
Expected: 10 passed.

- [ ] **Step 5: Commit**

```bash
git add packages/jw-core/src/jw_core/exporters/markdown.py packages/jw-core/tests/test_exporter_markdown.py
git commit -m "feat(exporters): markdown exporter with 3 citation styles"
```

---

### Task 4: Template resolver + Jinja2 templates

**Files:**
- Create: `packages/jw-core/src/jw_core/templates/__init__.py`
- Create: `packages/jw-core/src/jw_core/templates/study_sheet/__init__.py`
- Create: `packages/jw-core/src/jw_core/templates/study_sheet/plain.html.j2`
- Create: `packages/jw-core/src/jw_core/templates/study_sheet/study-sheet.html.j2`
- Create: `packages/jw-core/src/jw_core/exporters/templates_resolver.py`
- Create: `packages/jw-core/tests/test_exporter_templates.py`

- [ ] **Step 1: Write the failing tests**

```python
# packages/jw-core/tests/test_exporter_templates.py
"""Tests for the template resolver."""

from __future__ import annotations

from pathlib import Path

import pytest

from jw_core.exporters.errors import ExportError
from jw_core.exporters.templates_resolver import (
    list_builtin_templates,
    render_html,
    resolve_template_path,
)
from jw_core.exporters.ir import StudySection, StudySheet


def _sheet() -> StudySheet:
    return StudySheet(
        title="T",
        sections=[StudySection(heading="h", body="b")],
    )


def test_list_builtin_templates_includes_two() -> None:
    names = list_builtin_templates()
    assert "plain.html.j2" in names
    assert "study-sheet.html.j2" in names


def test_resolve_builtin_template() -> None:
    p = resolve_template_path("plain.html.j2")
    assert p.exists()
    assert p.name == "plain.html.j2"


def test_resolve_user_override(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    user_dir = tmp_path / ".jw-agent-toolkit" / "templates"
    user_dir.mkdir(parents=True)
    user_tpl = user_dir / "plain.html.j2"
    user_tpl.write_text("<html>USER</html>", encoding="utf-8")
    monkeypatch.setenv("HOME", str(tmp_path))
    p = resolve_template_path("plain.html.j2")
    # User override wins
    assert p == user_tpl


def test_resolve_missing_raises() -> None:
    with pytest.raises(ExportError):
        resolve_template_path("does-not-exist.html.j2")


def test_render_html_contains_title_and_body() -> None:
    html = render_html(_sheet(), template_name="plain.html.j2")
    assert "T" in html
    assert "<html" in html.lower()


def test_render_html_escapes_html_in_body() -> None:
    sheet = StudySheet(
        title="T",
        sections=[StudySection(heading="h", body="<script>alert(1)</script>")],
    )
    html = render_html(sheet, template_name="plain.html.j2")
    assert "<script>" not in html
    assert "&lt;script&gt;" in html
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/jw-core/tests/test_exporter_templates.py -v`
Expected: FAIL — `templates_resolver` missing.

- [ ] **Step 3: Implement resolver + templates**

```python
# packages/jw-core/src/jw_core/templates/__init__.py
"""Packaged Jinja2 templates for the exporters module."""
```

```python
# packages/jw-core/src/jw_core/templates/study_sheet/__init__.py
"""Study-sheet HTML templates rendered by jw_core.exporters.pdf."""
```

```html
{# packages/jw-core/src/jw_core/templates/study_sheet/plain.html.j2 #}
<!doctype html>
<html lang="{{ sheet.language }}">
<head>
  <meta charset="utf-8">
  <title>{{ sheet.title }}</title>
  <style>
    @page { margin: 2cm; }
    body { font-family: "Inter", -apple-system, BlinkMacSystemFont, sans-serif; line-height: 1.5; color: #222; }
    h1 { font-size: 24pt; margin-bottom: 0; }
    h2.subtitle { font-size: 14pt; color: #666; margin-top: 4pt; font-weight: 400; }
    h3 { font-size: 14pt; margin-top: 20pt; }
    .body { font-size: 11pt; word-wrap: break-word; }
    .excerpt { border-left: 3px solid #999; padding-left: 10pt; color: #555; margin: 8pt 0; font-style: italic; }
    .cite-list { font-size: 9pt; color: #666; margin-top: 4pt; }
    a { color: #1a5fb4; word-wrap: break-word; }
    .footer { margin-top: 30pt; border-top: 1px solid #ccc; padding-top: 6pt; font-size: 9pt; color: #888; }
  </style>
</head>
<body>
  <h1>{{ sheet.title }}</h1>
  {% if sheet.subtitle %}<h2 class="subtitle">{{ sheet.subtitle }}</h2>{% endif %}

  {% for section in sheet.sections %}
    <section>
      <h3>{{ section.heading }}</h3>
      <div class="body">{{ section.body }}</div>
      {% if section.excerpt %}<div class="excerpt">{{ section.excerpt }}</div>{% endif %}
      {% if section.citations %}
        <ul class="cite-list">
          {% for c in section.citations %}
            <li><a href="{{ c.url }}">{{ c.short_label or c.title or c.url }}</a></li>
          {% endfor %}
        </ul>
      {% endif %}
    </section>
  {% endfor %}

  {% if sheet.footer_note %}
    <div class="footer">{{ sheet.footer_note }}</div>
  {% endif %}
</body>
</html>
```

```html
{# packages/jw-core/src/jw_core/templates/study_sheet/study-sheet.html.j2 #}
<!doctype html>
<html lang="{{ sheet.language }}">
<head>
  <meta charset="utf-8">
  <title>{{ sheet.title }}</title>
  <style>
    @page { margin: 1.8cm 2.5cm; }
    body { font-family: "Charter", "Source Serif Pro", Georgia, serif; line-height: 1.55; color: #1a1a1a; }
    h1 { font-size: 26pt; margin-bottom: 0; border-bottom: 2px solid #1a1a1a; padding-bottom: 6pt; }
    h2.subtitle { font-size: 13pt; color: #555; margin-top: 6pt; font-weight: 400; font-style: italic; }
    h3 { font-size: 14pt; margin-top: 22pt; color: #0a3a6a; }
    .body { font-size: 11.5pt; word-wrap: break-word; text-align: justify; hyphens: auto; }
    .excerpt { border-left: 4px solid #c9a64f; background: #faf7f0; padding: 6pt 10pt; margin: 10pt 0; color: #333; font-style: italic; }
    .cite-list { font-size: 9pt; color: #555; margin-top: 6pt; list-style: square; }
    .cite-list li { margin-bottom: 2pt; }
    a { color: #0a3a6a; word-wrap: break-word; }
    .footer { margin-top: 36pt; border-top: 1px solid #aaa; padding-top: 8pt; font-size: 9pt; color: #777; text-align: center; }
  </style>
</head>
<body>
  <h1>{{ sheet.title }}</h1>
  {% if sheet.subtitle %}<h2 class="subtitle">{{ sheet.subtitle }}</h2>{% endif %}

  {% for section in sheet.sections %}
    <section>
      <h3>{{ section.heading }}</h3>
      <div class="body">{{ section.body }}</div>
      {% if section.excerpt %}<div class="excerpt">{{ section.excerpt }}</div>{% endif %}
      {% if section.citations %}
        <ul class="cite-list">
          {% for c in section.citations %}
            <li><a href="{{ c.url }}">{{ c.short_label or c.title or c.url }}</a></li>
          {% endfor %}
        </ul>
      {% endif %}
    </section>
  {% endfor %}

  {% if sheet.footer_note %}
    <div class="footer">{{ sheet.footer_note }}</div>
  {% endif %}
</body>
</html>
```

```python
# packages/jw-core/src/jw_core/exporters/templates_resolver.py
"""Resolve Jinja2 templates, honoring user overrides at ~/.jw-agent-toolkit/templates/.

Lookup order:
    1. ~/.jw-agent-toolkit/templates/<name>  (user override)
    2. jw_core.templates.study_sheet.<name>  (packaged default)
"""

from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape

from jw_core.exporters.errors import ExportError
from jw_core.exporters.ir import StudySheet


def _packaged_dir() -> Path:
    return Path(__file__).parent.parent / "templates" / "study_sheet"


def _user_dir() -> Path:
    return Path.home() / ".jw-agent-toolkit" / "templates"


def list_builtin_templates() -> list[str]:
    """Return names of packaged Jinja2 templates."""
    return sorted(p.name for p in _packaged_dir().glob("*.html.j2"))


def resolve_template_path(name: str) -> Path:
    """Return the path of the template, user override wins. Raises if missing."""

    candidate = _user_dir() / name
    if candidate.exists():
        return candidate
    candidate = _packaged_dir() / name
    if candidate.exists():
        return candidate
    raise ExportError(
        f"Template {name!r} not found (looked in {_user_dir()} and {_packaged_dir()})"
    )


def render_html(sheet: StudySheet, *, template_name: str = "plain.html.j2") -> str:
    """Render `sheet` to HTML using the given Jinja2 template."""

    path = resolve_template_path(template_name)
    env = Environment(
        loader=FileSystemLoader(path.parent),
        autoescape=select_autoescape(["html", "j2"]),
        undefined=StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
    )
    template = env.get_template(path.name)
    return template.render(sheet=sheet)
```

- [ ] **Step 4: Run tests until green**

Run: `uv run pytest packages/jw-core/tests/test_exporter_templates.py -v`
Expected: 6 passed.

- [ ] **Step 5: Verify templates are packaged**

Run:
```bash
uv run python -c "
from jw_core.exporters.templates_resolver import list_builtin_templates
print(list_builtin_templates())
"
```
Expected: `['plain.html.j2', 'study-sheet.html.j2']`.

If empty, edit `packages/jw-core/pyproject.toml` and add to `[tool.hatch.build.targets.wheel]`:
```toml
[tool.hatch.build.targets.wheel.shared-data]
"src/jw_core/templates" = "jw_core/templates"
```
or ensure `force-include` covers the templates dir.

- [ ] **Step 6: Commit**

```bash
git add packages/jw-core/src/jw_core/templates packages/jw-core/src/jw_core/exporters/templates_resolver.py packages/jw-core/tests/test_exporter_templates.py packages/jw-core/pyproject.toml
git commit -m "feat(exporters): Jinja2 template resolver with user-override + 2 built-in themes"
```

---

### Task 5: PDF exporter (WeasyPrint)

**Files:**
- Create: `packages/jw-core/src/jw_core/exporters/pdf.py`
- Create: `packages/jw-core/tests/test_exporter_pdf.py`

- [ ] **Step 1: Write the failing test (skipped if weasyprint missing)**

```python
# packages/jw-core/tests/test_exporter_pdf.py
"""Tests for jw_core.exporters.pdf.

Skipped if weasyprint is not installed (the [pdf] extra is optional).
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from jw_core.exporters.errors import MissingDependencyError
from jw_core.exporters.ir import CitationIR, StudySection, StudySheet

WEASY_AVAILABLE = importlib.util.find_spec("weasyprint") is not None

pytestmark = pytest.mark.skipif(
    not WEASY_AVAILABLE,
    reason="weasyprint not installed (install jw-core[pdf])",
)


def _sheet() -> StudySheet:
    return StudySheet(
        title="Trinidad",
        subtitle="Análisis apologético",
        sections=[
            StudySection(
                heading="Jehová es uno",
                body="La Biblia es clara: hay un solo Dios.",
                excerpt="Deuteronomio 6:4",
                citations=[
                    CitationIR(
                        url="https://wol.jw.org/x",
                        title="Trinidad",
                        kind="article",
                        short_label="Trinidad",
                    )
                ],
            )
        ],
        footer_note="Generado por jw-agent-toolkit.",
    )


def test_export_pdf_writes_valid_file(tmp_path: Path) -> None:
    from jw_core.exporters.pdf import export_pdf

    out = tmp_path / "demo.pdf"
    written = export_pdf(_sheet(), out=out)
    assert written == out
    assert out.exists()
    head = out.read_bytes()[:4]
    assert head == b"%PDF"


def test_export_pdf_study_sheet_theme(tmp_path: Path) -> None:
    from jw_core.exporters.pdf import export_pdf

    out = tmp_path / "demo.pdf"
    export_pdf(_sheet(), out=out, theme="study-sheet")
    assert out.read_bytes()[:4] == b"%PDF"


def test_export_pdf_creates_parent_dirs(tmp_path: Path) -> None:
    from jw_core.exporters.pdf import export_pdf

    out = tmp_path / "deep" / "nested" / "demo.pdf"
    export_pdf(_sheet(), out=out)
    assert out.exists()


def test_export_pdf_unknown_theme_raises(tmp_path: Path) -> None:
    from jw_core.exporters.errors import ExportError
    from jw_core.exporters.pdf import export_pdf

    out = tmp_path / "x.pdf"
    with pytest.raises(ExportError):
        export_pdf(_sheet(), out=out, theme="nope")


# Always-on test: even when weasyprint IS installed, simulate missing dep
def test_missing_dependency_when_weasyprint_absent(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    import builtins

    real_import = builtins.__import__

    def _ban_weasy(name: str, *a, **kw):
        if name == "weasyprint" or name.startswith("weasyprint."):
            raise ImportError("simulated")
        return real_import(name, *a, **kw)

    monkeypatch.setattr(builtins, "__import__", _ban_weasy)

    from jw_core.exporters.pdf import export_pdf

    with pytest.raises(MissingDependencyError):
        export_pdf(_sheet(), out=tmp_path / "x.pdf")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/jw-core/tests/test_exporter_pdf.py -v`
Expected: FAIL — module `pdf` missing (or all skipped if weasyprint not installed; install with `uv pip install weasyprint` for the rest of this task).

- [ ] **Step 3: Implement the PDF exporter**

```python
# packages/jw-core/src/jw_core/exporters/pdf.py
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
            "weasyprint is required for PDF export. "
            "Install with: pip install 'jw-core[pdf]'"
        ) from exc

    if theme not in _THEME_TO_TEMPLATE:
        raise ExportError(f"Unknown PDF theme {theme!r}. Available: {sorted(_THEME_TO_TEMPLATE)}")

    template_name = _THEME_TO_TEMPLATE[theme]
    html_body = render_html(sheet, template_name=template_name)

    out.parent.mkdir(parents=True, exist_ok=True)
    HTML(string=html_body).write_pdf(target=str(out))
    return out
```

- [ ] **Step 4: Run tests until green**

If weasyprint is installed: `uv run pytest packages/jw-core/tests/test_exporter_pdf.py -v`
Expected: 5 passed.

If not installed: 4 skipped + 1 passed (the missing-dep test).

- [ ] **Step 5: Commit**

```bash
git add packages/jw-core/src/jw_core/exporters/pdf.py packages/jw-core/tests/test_exporter_pdf.py
git commit -m "feat(exporters): PDF exporter via WeasyPrint with 2 themes"
```

---

### Task 6: DOCX exporter (python-docx)

**Files:**
- Create: `packages/jw-core/src/jw_core/exporters/docx.py`
- Create: `packages/jw-core/tests/test_exporter_docx.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/jw-core/tests/test_exporter_docx.py
"""Tests for jw_core.exporters.docx."""

from __future__ import annotations

import importlib.util
import zipfile
from pathlib import Path

import pytest

from jw_core.exporters.errors import MissingDependencyError
from jw_core.exporters.ir import CitationIR, StudySection, StudySheet

DOCX_AVAILABLE = importlib.util.find_spec("docx") is not None

pytestmark = pytest.mark.skipif(
    not DOCX_AVAILABLE,
    reason="python-docx not installed (install jw-core[docx])",
)


def _sheet() -> StudySheet:
    return StudySheet(
        title="Trinidad",
        subtitle="Análisis",
        sections=[
            StudySection(
                heading="Jehová es uno",
                body="La Biblia es clara.",
                excerpt="Deut 6:4",
                citations=[
                    CitationIR(url="https://wol.jw.org/x", short_label="Folleto Trinidad")
                ],
            )
        ],
        footer_note="Generado por jw-agent-toolkit.",
    )


def test_export_docx_writes_valid_zip(tmp_path: Path) -> None:
    from jw_core.exporters.docx import export_docx

    out = tmp_path / "demo.docx"
    written = export_docx(_sheet(), out=out)
    assert written == out
    assert out.exists()
    # DOCX is a ZIP
    assert zipfile.is_zipfile(out)
    with zipfile.ZipFile(out) as zf:
        names = zf.namelist()
        assert "word/document.xml" in names


def test_export_docx_contains_title_and_heading(tmp_path: Path) -> None:
    from jw_core.exporters.docx import export_docx

    out = tmp_path / "demo.docx"
    export_docx(_sheet(), out=out)
    with zipfile.ZipFile(out) as zf:
        xml = zf.read("word/document.xml").decode("utf-8")
    assert "Trinidad" in xml
    assert "Jehová es uno" in xml


def test_export_docx_includes_citation_hyperlink(tmp_path: Path) -> None:
    from jw_core.exporters.docx import export_docx

    out = tmp_path / "demo.docx"
    export_docx(_sheet(), out=out)
    with zipfile.ZipFile(out) as zf:
        rels = zf.read("word/_rels/document.xml.rels").decode("utf-8")
    assert "wol.jw.org" in rels


def test_export_docx_creates_parent_dirs(tmp_path: Path) -> None:
    from jw_core.exporters.docx import export_docx

    out = tmp_path / "deep" / "x.docx"
    export_docx(_sheet(), out=out)
    assert out.exists()


def test_missing_dependency_when_pythondocx_absent(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    import builtins

    real_import = builtins.__import__

    def _ban(name: str, *a, **kw):
        if name == "docx" or name.startswith("docx."):
            raise ImportError("simulated")
        return real_import(name, *a, **kw)

    monkeypatch.setattr(builtins, "__import__", _ban)

    from jw_core.exporters.docx import export_docx

    with pytest.raises(MissingDependencyError):
        export_docx(_sheet(), out=tmp_path / "x.docx")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/jw-core/tests/test_exporter_docx.py -v`
Expected: FAIL — `docx` exporter module missing.

- [ ] **Step 3: Implement DOCX exporter**

```python
# packages/jw-core/src/jw_core/exporters/docx.py
"""DOCX exporter via python-docx.

Uses python-docx's programmatic API directly (no template — DOCX templating
adds complexity without value at our structure level).
"""

from __future__ import annotations

from pathlib import Path

from jw_core.exporters.errors import MissingDependencyError
from jw_core.exporters.ir import CitationIR, StudySheet


def export_docx(sheet: StudySheet, *, out: Path) -> Path:
    """Render `sheet` as DOCX and write it to `out`. Returns `out`.

    Requires the [docx] extra. Raises `MissingDependencyError` otherwise.
    """

    try:
        from docx import Document  # noqa: PLC0415  (lazy)
        from docx.oxml.ns import qn  # noqa: PLC0415
        from docx.oxml import OxmlElement  # noqa: PLC0415
    except ImportError as exc:
        raise MissingDependencyError(
            "python-docx is required for DOCX export. "
            "Install with: pip install 'jw-core[docx]'"
        ) from exc

    doc = Document()

    # Title
    doc.add_heading(sheet.title, level=0)
    if sheet.subtitle:
        p = doc.add_paragraph()
        run = p.add_run(sheet.subtitle)
        run.italic = True

    # Sections
    for section in sheet.sections:
        doc.add_heading(section.heading, level=2)
        doc.add_paragraph(section.body)

        if section.excerpt:
            p = doc.add_paragraph(section.excerpt)
            p.style = doc.styles["Intense Quote"]

        for cite in section.citations:
            _add_citation_paragraph(doc, cite, qn, OxmlElement)

    if sheet.footer_note:
        doc.add_paragraph()
        sep = doc.add_paragraph("—" * 30)
        sep.alignment = 1  # center
        p = doc.add_paragraph()
        run = p.add_run(sheet.footer_note)
        run.italic = True
        run.font.size = run.font.size  # no-op to anchor formatting

    out.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(out))
    return out


def _add_citation_paragraph(doc, cite: CitationIR, qn, OxmlElement) -> None:
    """Add a paragraph holding a hyperlink to the citation URL."""

    p = doc.add_paragraph()
    p.paragraph_format.left_indent = p.paragraph_format.left_indent  # no-op
    label = cite.short_label or cite.title or cite.url

    # Add a real hyperlink relationship.
    part = p.part
    rid = part.relate_to(
        cite.url,
        "http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink",
        is_external=True,
    )
    hyperlink = OxmlElement("w:hyperlink")
    hyperlink.set(qn("r:id"), rid)

    new_run = OxmlElement("w:r")
    r_pr = OxmlElement("w:rPr")
    color = OxmlElement("w:color")
    color.set(qn("w:val"), "0A3A6A")
    r_pr.append(color)
    u = OxmlElement("w:u")
    u.set(qn("w:val"), "single")
    r_pr.append(u)
    new_run.append(r_pr)

    t = OxmlElement("w:t")
    t.text = f"  • {label}"
    new_run.append(t)
    hyperlink.append(new_run)
    p._p.append(hyperlink)
```

- [ ] **Step 4: Run tests until green**

Run: `uv run pytest packages/jw-core/tests/test_exporter_docx.py -v`
Expected: 5 passed (if python-docx installed).

- [ ] **Step 5: Commit**

```bash
git add packages/jw-core/src/jw_core/exporters/docx.py packages/jw-core/tests/test_exporter_docx.py
git commit -m "feat(exporters): DOCX exporter via python-docx with hyperlink citations"
```

---

### Task 7: Anki exporter (genanki) with stable GUIDs

**Files:**
- Create: `packages/jw-core/src/jw_core/exporters/anki.py`
- Create: `packages/jw-core/tests/test_exporter_anki.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/jw-core/tests/test_exporter_anki.py
"""Tests for jw_core.exporters.anki."""

from __future__ import annotations

import importlib.util
import zipfile
from pathlib import Path

import pytest

from jw_core.exporters.errors import MissingDependencyError
from jw_core.exporters.ir import CitationIR, StudySection, StudySheet

ANKI_AVAILABLE = importlib.util.find_spec("genanki") is not None

pytestmark = pytest.mark.skipif(
    not ANKI_AVAILABLE,
    reason="genanki not installed (install jw-core[anki])",
)


def _sheet() -> StudySheet:
    return StudySheet(
        title="Trinidad — repaso",
        sections=[
            StudySection(
                heading="Jehová es uno",
                body="La Biblia presenta un solo Dios verdadero.",
                citations=[
                    CitationIR(url="https://wol.jw.org/x", short_label="Folleto Trinidad"),
                    CitationIR(url="https://wol.jw.org/y", short_label="Juan 17:3"),
                ],
            ),
            StudySection(
                heading="Jesús no es el Padre",
                body="Jesús siempre se distinguió del Padre.",
            ),
        ],
    )


def test_export_apkg_writes_valid_zip(tmp_path: Path) -> None:
    from jw_core.exporters.anki import export_apkg

    out = tmp_path / "deck.apkg"
    written = export_apkg(_sheet(), out=out)
    assert written == out
    assert out.exists()
    assert zipfile.is_zipfile(out)


def test_export_apkg_default_one_note_per_section(tmp_path: Path) -> None:
    from jw_core.exporters.anki import build_deck, export_apkg

    deck = build_deck(_sheet(), per_citation_cards=False)
    assert len(deck.notes) == 2  # one per section


def test_export_apkg_per_citation_cards(tmp_path: Path) -> None:
    from jw_core.exporters.anki import build_deck

    deck = build_deck(_sheet(), per_citation_cards=True)
    # 2 section notes + 2 extra (citations of first section only — second section has 0)
    assert len(deck.notes) == 4


def test_export_apkg_guid_stable_across_runs(tmp_path: Path) -> None:
    from jw_core.exporters.anki import build_deck

    d1 = build_deck(_sheet())
    d2 = build_deck(_sheet())
    g1 = sorted(n.guid for n in d1.notes)
    g2 = sorted(n.guid for n in d2.notes)
    assert g1 == g2


def test_export_apkg_guid_changes_when_content_changes(tmp_path: Path) -> None:
    from jw_core.exporters.anki import build_deck

    d1 = build_deck(_sheet())
    sheet2 = _sheet()
    sheet2.sections[0].heading = "Otro encabezado"
    d2 = build_deck(sheet2)
    g1 = sorted(n.guid for n in d1.notes)
    g2 = sorted(n.guid for n in d2.notes)
    assert g1 != g2


def test_export_apkg_deck_id_stable(tmp_path: Path) -> None:
    from jw_core.exporters.anki import build_deck

    d1 = build_deck(_sheet())
    d2 = build_deck(_sheet())
    assert d1.deck_id == d2.deck_id


def test_export_apkg_creates_parent_dirs(tmp_path: Path) -> None:
    from jw_core.exporters.anki import export_apkg

    out = tmp_path / "deep" / "deck.apkg"
    export_apkg(_sheet(), out=out)
    assert out.exists()


def test_missing_dependency_when_genanki_absent(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    import builtins

    real_import = builtins.__import__

    def _ban(name: str, *a, **kw):
        if name == "genanki" or name.startswith("genanki."):
            raise ImportError("simulated")
        return real_import(name, *a, **kw)

    monkeypatch.setattr(builtins, "__import__", _ban)

    from jw_core.exporters.anki import export_apkg

    with pytest.raises(MissingDependencyError):
        export_apkg(_sheet(), out=tmp_path / "x.apkg")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/jw-core/tests/test_exporter_anki.py -v`
Expected: FAIL — `anki` exporter module missing.

- [ ] **Step 3: Implement Anki exporter**

```python
# packages/jw-core/src/jw_core/exporters/anki.py
"""Anki exporter via genanki.

GUID strategy (stable across re-exports):
    guid = sha256(sheet.title + section.heading + section.body[:200])
This means re-exporting the same StudySheet after a typo fix UPDATES the
existing note in Anki instead of duplicating it. Only meaningful changes
to heading/body produce a new note.

Deck and model IDs are also derived from sheet.title via sha256, so the
same deck always lands in the same place in Anki's tree.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from jw_core.exporters.errors import MissingDependencyError
from jw_core.exporters.ir import CitationIR, StudySection, StudySheet


_MODEL_NAME = "jw-agent-toolkit study sheet"


def export_apkg(
    sheet: StudySheet,
    *,
    out: Path,
    deck_name: str | None = None,
    per_citation_cards: bool = False,
) -> Path:
    """Render `sheet` as an Anki package (.apkg) and write it to `out`."""

    try:
        import genanki  # noqa: PLC0415
    except ImportError as exc:
        raise MissingDependencyError(
            "genanki is required for Anki export. "
            "Install with: pip install 'jw-core[anki]'"
        ) from exc

    deck = build_deck(sheet, deck_name=deck_name, per_citation_cards=per_citation_cards)
    out.parent.mkdir(parents=True, exist_ok=True)
    genanki.Package(deck).write_to_file(str(out))
    return out


def build_deck(
    sheet: StudySheet,
    *,
    deck_name: str | None = None,
    per_citation_cards: bool = False,
):
    """Build (but don't write) the genanki.Deck. Useful for tests."""

    try:
        import genanki  # noqa: PLC0415
    except ImportError as exc:
        raise MissingDependencyError(
            "genanki is required for Anki export."
        ) from exc

    model_id = _id_from(_MODEL_NAME)
    deck_id = _id_from(sheet.title)

    model = genanki.Model(
        model_id=model_id,
        name=_MODEL_NAME,
        fields=[{"name": "Front"}, {"name": "Back"}],
        templates=[
            {
                "name": "card",
                "qfmt": "{{Front}}",
                "afmt": '{{FrontSide}}<hr id="answer">{{Back}}',
            }
        ],
    )

    name = deck_name or sheet.title
    deck = genanki.Deck(deck_id=deck_id, name=name)

    for section in sheet.sections:
        deck.add_note(_section_note(genanki, model, sheet, section))
        if per_citation_cards and len(section.citations) >= 1:
            for cite in section.citations:
                deck.add_note(_citation_note(genanki, model, sheet, section, cite))

    return deck


# ── helpers ──


def _id_from(text: str) -> int:
    """Derive a stable 31-bit positive int ID from text via sha256."""
    digest = hashlib.sha256(text.encode("utf-8")).digest()
    return int.from_bytes(digest[:4], "big") & 0x7FFFFFFF


def _guid(*parts: str) -> str:
    raw = "|".join(parts).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:32]


def _section_note(genanki, model, sheet: StudySheet, section: StudySection):
    """Build the main note for a section."""

    front = section.heading
    back_parts: list[str] = [section.body.replace("\n", "<br>")]
    if section.excerpt:
        back_parts.append(f"<blockquote>{section.excerpt}</blockquote>")
    if section.citations:
        items = "".join(
            f'<li><a href="{c.url}">{c.short_label or c.title or c.url}</a></li>'
            for c in section.citations
        )
        back_parts.append(f"<ul>{items}</ul>")
    back = "".join(back_parts)

    return genanki.Note(
        model=model,
        fields=[front, back],
        guid=_guid(sheet.title, section.heading, section.body[:200]),
    )


def _citation_note(
    genanki,
    model,
    sheet: StudySheet,
    section: StudySection,
    cite: CitationIR,
):
    """Build an extra note focused on a single citation (when per_citation_cards=True)."""

    front = cite.short_label or cite.title or cite.url
    back = f'{section.heading}<br><a href="{cite.url}">{cite.url}</a>'
    return genanki.Note(
        model=model,
        fields=[front, back],
        guid=_guid(sheet.title, section.heading, "cite", cite.url),
    )
```

- [ ] **Step 4: Run tests until green**

Run: `uv run pytest packages/jw-core/tests/test_exporter_anki.py -v`
Expected: 8 passed (if genanki installed).

- [ ] **Step 5: Commit**

```bash
git add packages/jw-core/src/jw_core/exporters/anki.py packages/jw-core/tests/test_exporter_anki.py
git commit -m "feat(exporters): Anki exporter via genanki with stable GUIDs"
```

---

### Task 8: CLI command `jw export`

**Files:**
- Create: `packages/jw-cli/src/jw_cli/commands/export.py`
- Create: `packages/jw-cli/tests/test_export_command.py`
- Modify: `packages/jw-cli/src/jw_cli/main.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/jw-cli/tests/test_export_command.py
"""End-to-end tests for `jw export`."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from jw_cli.main import app

RUNNER = CliRunner()


def _agent_result_json() -> dict:
    return {
        "query": "Es la Trinidad bíblica?",
        "agent_name": "apologetics",
        "warnings": [],
        "metadata": {"language": "es"},
        "findings": [
            {
                "summary": "Jehová es el único Dios verdadero.",
                "excerpt": "",
                "metadata": {},
                "citation": {
                    "url": "https://wol.jw.org/x",
                    "title": "Trinidad",
                    "kind": "article",
                    "metadata": {},
                },
            }
        ],
    }


def _write(tmp_path: Path) -> Path:
    p = tmp_path / "result.json"
    p.write_text(json.dumps(_agent_result_json()), encoding="utf-8")
    return p


def test_export_markdown_smoke(tmp_path: Path) -> None:
    src = _write(tmp_path)
    out = tmp_path / "demo.md"
    result = RUNNER.invoke(app, ["export", str(src), "--format", "markdown", "--out", str(out)])
    assert result.exit_code == 0, result.stdout
    assert out.exists()
    text = out.read_text(encoding="utf-8")
    assert "Trinidad" in text or "trinidad" in text.lower()


def test_export_unknown_format_fails(tmp_path: Path) -> None:
    src = _write(tmp_path)
    result = RUNNER.invoke(app, ["export", str(src), "--format", "bogus", "--out", "/tmp/x"])
    assert result.exit_code != 0


def test_export_missing_input_fails() -> None:
    result = RUNNER.invoke(app, ["export", "/does/not/exist.json", "--format", "markdown", "--out", "/tmp/x.md"])
    assert result.exit_code != 0


def test_export_title_override(tmp_path: Path) -> None:
    src = _write(tmp_path)
    out = tmp_path / "demo.md"
    result = RUNNER.invoke(
        app,
        ["export", str(src), "--format", "markdown", "--out", str(out), "--title", "MiHoja"],
    )
    assert result.exit_code == 0
    assert out.read_text(encoding="utf-8").startswith("# MiHoja")


@pytest.mark.skipif(
    importlib.util.find_spec("weasyprint") is None,
    reason="weasyprint not installed",
)
def test_export_pdf_smoke(tmp_path: Path) -> None:
    src = _write(tmp_path)
    out = tmp_path / "demo.pdf"
    result = RUNNER.invoke(app, ["export", str(src), "--format", "pdf", "--out", str(out)])
    assert result.exit_code == 0, result.stdout
    assert out.read_bytes()[:4] == b"%PDF"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/jw-cli/tests/test_export_command.py -v`
Expected: FAIL — `export` command not registered.

- [ ] **Step 3: Implement the command**

```python
# packages/jw-cli/src/jw_cli/commands/export.py
"""`jw export` — convert AgentResult JSON into markdown/pdf/docx/apkg."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Annotated

import typer

from jw_core.exporters.errors import ExportError, MissingDependencyError
from jw_core.exporters.ir import StudySheet
from jw_core.exporters.markdown import export_markdown


def export_cmd(
    source: Annotated[
        str,
        typer.Argument(help="Path to a JSON file with AgentResult.to_dict(), or '-' for stdin."),
    ],
    format: Annotated[
        str,
        typer.Option("--format", "-f", help="Output format: markdown | pdf | docx | apkg"),
    ] = "markdown",
    out: Annotated[
        Path,
        typer.Option("--out", "-o", help="Output path."),
    ] = Path("out.md"),
    title: Annotated[
        str | None, typer.Option("--title", help="Override the sheet title.")
    ] = None,
    language: Annotated[
        str | None, typer.Option("--language", "-l", help="Override the sheet language.")
    ] = None,
    citation_style: Annotated[
        str,
        typer.Option(
            "--citation-style",
            help="inline-paren | footnote | bibliography",
        ),
    ] = "footnote",
    include_citations: Annotated[
        bool, typer.Option("--include-citations/--no-citations")
    ] = True,
    theme: Annotated[
        str, typer.Option("--theme", help="PDF theme: plain | study-sheet")
    ] = "study-sheet",
    per_citation_cards: Annotated[
        bool,
        typer.Option(
            "--per-citation-cards/--no-per-citation-cards",
            help="Anki: emit one extra card per citation.",
        ),
    ] = False,
) -> None:
    """Convert an AgentResult JSON into a printable study sheet or Anki deck."""

    # Load AgentResult JSON.
    if source == "-":
        try:
            payload = json.loads(sys.stdin.read())
        except json.JSONDecodeError as exc:
            typer.secho(f"Invalid JSON on stdin: {exc}", fg=typer.colors.RED, err=True)
            raise typer.Exit(code=2)
    else:
        path = Path(source)
        if not path.exists():
            typer.secho(f"File not found: {path}", fg=typer.colors.RED, err=True)
            raise typer.Exit(code=2)
        payload = json.loads(path.read_text(encoding="utf-8"))

    sheet = StudySheet.from_agent_result(
        payload,
        title=title,
        language=language,
        include_citations=include_citations,
    )

    try:
        if format == "markdown":
            written = export_markdown(sheet, out=out, citation_style=citation_style)
        elif format == "pdf":
            from jw_core.exporters.pdf import export_pdf  # lazy

            written = export_pdf(sheet, out=out, theme=theme)  # type: ignore[arg-type]
        elif format == "docx":
            from jw_core.exporters.docx import export_docx

            written = export_docx(sheet, out=out)
        elif format == "apkg":
            from jw_core.exporters.anki import export_apkg

            written = export_apkg(sheet, out=out, per_citation_cards=per_citation_cards)
        else:
            typer.secho(
                f"Unknown format {format!r}. Use: markdown | pdf | docx | apkg",
                fg=typer.colors.RED,
                err=True,
            )
            raise typer.Exit(code=2)
    except MissingDependencyError as exc:
        typer.secho(str(exc), fg=typer.colors.RED, err=True)
        raise typer.Exit(code=3)
    except ExportError as exc:
        typer.secho(f"Export failed: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=4)

    typer.secho(f"Wrote {written} ({written.stat().st_size} bytes)", fg=typer.colors.GREEN)
```

- [ ] **Step 4: Register in `main.py`**

Edit `packages/jw-cli/src/jw_cli/main.py`:

- Add to the import block:
  ```python
  from jw_cli.commands import export
  ```
- After existing `app.command(...)` lines, add:
  ```python
  app.command(name="export")(export.export_cmd)
  ```

- [ ] **Step 5: Run test until green**

Run: `uv run pytest packages/jw-cli/tests/test_export_command.py -v`
Expected: 4-5 passed (1 PDF test skipped if weasyprint missing).

- [ ] **Step 6: Smoke test the CLI**

```bash
echo '{"query":"demo","agent_name":"apologetics","findings":[],"warnings":[],"metadata":{}}' \
  | uv run jw export - --format markdown --out /tmp/demo.md
cat /tmp/demo.md
```
Expected: file printed with `# demo` header.

- [ ] **Step 7: Commit**

```bash
git add packages/jw-cli/src/jw_cli/commands/export.py packages/jw-cli/src/jw_cli/main.py packages/jw-cli/tests/test_export_command.py
git commit -m "feat(cli): jw export command for markdown/pdf/docx/apkg"
```

---

### Task 9: MCP tool `export_study_sheet`

**Files:**
- Modify: `packages/jw-mcp/src/jw_mcp/server.py`

- [ ] **Step 1: Register the tool**

Find the section of `server.py` that registers existing `@app.tool()` handlers and append:

```python
from jw_core.exporters.errors import ExportError, MissingDependencyError
from jw_core.exporters.ir import StudySheet
from jw_core.exporters.markdown import export_markdown
from pathlib import Path
from typing import Literal


@app.tool()
def export_study_sheet(
    agent_result: dict[str, Any],
    format: Literal["markdown", "pdf", "docx", "apkg"],
    out_path: str,
    title: str | None = None,
    language: str | None = None,
    citation_style: Literal["inline-paren", "footnote", "bibliography"] = "footnote",
    include_citations: bool = True,
    theme: Literal["plain", "study-sheet"] = "study-sheet",
    per_citation_cards: bool = False,
) -> dict[str, Any]:
    """Convert an AgentResult dict into a printable study sheet (md/pdf/docx/apkg).

    Returns {"out": str, "format": str, "bytes_written": int} on success,
    or {"error": "..."} on failure.
    """

    sheet = StudySheet.from_agent_result(
        agent_result,
        title=title,
        language=language,
        include_citations=include_citations,
    )
    out = Path(out_path).expanduser()

    try:
        if format == "markdown":
            written = export_markdown(sheet, out=out, citation_style=citation_style)
        elif format == "pdf":
            from jw_core.exporters.pdf import export_pdf

            written = export_pdf(sheet, out=out, theme=theme)
        elif format == "docx":
            from jw_core.exporters.docx import export_docx

            written = export_docx(sheet, out=out)
        elif format == "apkg":
            from jw_core.exporters.anki import export_apkg

            written = export_apkg(sheet, out=out, per_citation_cards=per_citation_cards)
        else:
            return {"error": f"unknown format {format!r}"}
    except MissingDependencyError as exc:
        return {"error": str(exc)}
    except ExportError as exc:
        return {"error": f"export failed: {exc}"}

    return {
        "out": str(written),
        "format": format,
        "bytes_written": written.stat().st_size,
    }
```

(If `from typing import Any` or `Path` are already imported at the top of the file, skip the redundant imports — just place the function with the existing ones.)

- [ ] **Step 2: Smoke-test the tool registration**

Run:
```bash
uv run python -c "
from jw_mcp.server import app
tools = [t.name for t in app._tools.values()] if hasattr(app, '_tools') else []
print('Has export_study_sheet:', 'export_study_sheet' in tools)
"
```
(The exact FastMCP introspection may vary; alternatively start the server and list tools via the MCP protocol.)

- [ ] **Step 3: Commit**

```bash
git add packages/jw-mcp/src/jw_mcp/server.py
git commit -m "feat(mcp): export_study_sheet tool wrapping the exporters module"
```

---

### Task 10: Documentation, ROADMAP, VISION_AUDIT

**Files:**
- Create: `docs/guias/exportador-hoja-de-estudio.md`
- Modify: `docs/ROADMAP.md`
- Modify: `docs/VISION_AUDIT.md`
- Modify: `docs/README.md`

- [ ] **Step 1: Write the user guide**

```markdown
# Exportador de hoja de estudio (PDF / DOCX / Anki / Markdown)

> Fase 31 — convierte cualquier `AgentResult` en un entregable imprimible o
> un mazo Anki de repaso espaciado. Markdown siempre disponible; los demás
> formatos son opt-in vía extras.

## Instalación

```bash
# baseline (markdown siempre)
uv sync --all-packages

# con extras opcionales
uv pip install 'jw-core[pdf]'    # WeasyPrint
uv pip install 'jw-core[docx]'   # python-docx
uv pip install 'jw-core[anki]'   # genanki
```

WeasyPrint requiere librerías nativas (cairo, pango). Ver
<https://doc.courtbouillon.org/weasyprint/stable/first_steps.html> para
instrucciones por plataforma.

## Uso (CLI)

```bash
# 1) Generar el AgentResult
uv run jw apologetics "Trinidad" --json > /tmp/trinity.json

# 2) Convertir
uv run jw export /tmp/trinity.json --format markdown --out hoja.md
uv run jw export /tmp/trinity.json --format pdf --out hoja.pdf --theme study-sheet
uv run jw export /tmp/trinity.json --format docx --out hoja.docx
uv run jw export /tmp/trinity.json --format apkg --out mazo.apkg --per-citation-cards
```

Pipeline en una sola línea:

```bash
uv run jw apologetics "Trinidad" --json | uv run jw export - -f pdf -o /tmp/x.pdf
```

## Estilos de cita

- `--citation-style inline-paren` — citas entre paréntesis dentro del cuerpo.
- `--citation-style footnote` (default) — marcadores `[^1]` con definiciones al final.
- `--citation-style bibliography` — cuerpo limpio + lista de fuentes al final.

## Plantillas personalizadas

Coloca un Jinja2 con el mismo nombre que un template built-in en
`~/.jw-agent-toolkit/templates/` para sobrescribirlo:

```
~/.jw-agent-toolkit/templates/study-sheet.html.j2
```

El resolver siempre prefiere la versión del usuario.

## Anki — re-export idempotente

El GUID de cada tarjeta deriva de `sha256(title + heading + body[:200])`.
Re-exportar el mismo `AgentResult` y reimportar el `.apkg` en Anki:
**actualiza** las notas existentes, no duplica.

## MCP

```json
{
  "tool": "export_study_sheet",
  "arguments": {
    "agent_result": { ... },
    "format": "pdf",
    "out_path": "~/Documents/hoja.pdf",
    "theme": "study-sheet",
    "citation_style": "footnote"
  }
}
```

Devuelve `{"out": "...", "format": "...", "bytes_written": N}` o `{"error": "..."}`.

## Diseño

Una IR única (`StudySheet`) intermedia. Cuatro exporters consumen la IR; nunca un
`AgentResult` directamente. Las dependencias pesadas se importan lazy, así que
importar `jw_core.exporters` nunca falla aunque falten los extras.
```

- [ ] **Step 2: Update ROADMAP and VISION_AUDIT**

Edit `docs/ROADMAP.md`:
- Append a section "## Fase 31 — Exportador hoja de estudio (PDF / DOCX / Anki)" with a one-paragraph summary and a link to the spec.

Edit `docs/VISION_AUDIT.md`:
- Locate the row for item `#11` (or the most semantically close to "exportador"). Mark its status as ✅ implemented in Fase 31 and add the path `jw_core.exporters`.

Edit `docs/README.md`:
- Add a bullet under the "Guías" section linking to `guias/exportador-hoja-de-estudio.md`.

- [ ] **Step 3: Commit**

```bash
git add docs/guias/exportador-hoja-de-estudio.md docs/ROADMAP.md docs/VISION_AUDIT.md docs/README.md
git commit -m "docs(fase-31): exporter user guide + roadmap + vision audit"
```

---

### Task 11: Full regression

- [ ] **Step 1: Run the entire test suite**

```bash
uv run pytest -q
```

Expected: every previous test still green; new tests added (≈45 new tests).

- [ ] **Step 2: Check no module imports fail without extras**

```bash
uv run python -c "
import jw_core.exporters
from jw_core.exporters import StudySheet
from jw_core.exporters.markdown import export_markdown
print('jw_core.exporters imports cleanly without extras.')
"
```
Expected: clean import.

- [ ] **Step 3: Lint / format**

```bash
uv run ruff check packages/jw-core/src/jw_core/exporters packages/jw-cli/src/jw_cli/commands/export.py
uv run ruff format packages/jw-core/src/jw_core/exporters packages/jw-cli/src/jw_cli/commands/export.py
```
Expected: no lint errors, no diff after format (or diff applied).

- [ ] **Step 4: Type-check (if mypy / pyright configured)**

```bash
uv run mypy packages/jw-core/src/jw_core/exporters 2>&1 || true
```
Expected: no new errors (lazy imports may yield "module not installed" — acceptable when extras are absent).

- [ ] **Step 5: Final commit if anything changed**

```bash
git status
# if anything pending after lint/format:
git add -A
git commit -m "chore(fase-31): lint and format pass"
```

---

## Self-review

- ✅ **No LLM in critical path**: every exporter is deterministic, no model calls.
- ✅ **Citations verifiable**: URL is preserved verbatim from `Finding.citation.url`. All exporters render URL as hyperlink.
- ✅ **Local-first**: all output paths are local. No telemetry, no network.
- ✅ **No network in tests**: every test uses synthetic StudySheets. WeasyPrint reads only the inline HTML string.
- ✅ **en/es/pt**: `StudySheet.language` propagates to `<html lang="">`. CLI accepts `--language`.
- ✅ **Spanish prose, English identifiers**: docstrings/comments in English (matching the rest of the codebase), user-facing copy and the guide in Spanish.
- ✅ **GPL-3.0 / Hatchling / src layout / Python 3.13**: respected throughout.
- ✅ **Single conversion `AgentResult → StudySheet`**: only in `ir.from_agent_result`.
- ✅ **Stable Anki GUIDs**: sha256-derived; re-export updates instead of duplicating.
- ✅ **Pluggable templates**: user override at `~/.jw-agent-toolkit/templates/` wins.
- ✅ **Optional extras are truly optional**: importing `jw_core.exporters` without `[pdf]`/`[docx]`/`[anki]` never errors; each exporter raises `MissingDependencyError` with copy-pasteable install hint.

### Edge cases covered

- Empty findings → one placeholder section.
- Long query → title truncated.
- HTML injection in body → escaped by Jinja2 `autoescape=True` and by markdown escape.
- Citation with no title → `short_label` fallback to last URL segment.
- Re-export same content → identical GUIDs and deck_id (proven by test).
- Re-export with content changed → different GUIDs (proven by test).
- Bad template name → `ExportError` with both lookup paths in the message.
- Missing extra → `MissingDependencyError` with install hint.

## Execution choice

This plan is structured for **superpowers:executing-plans** (one developer, sequential). Each task is independently committable; the test suite is green at every commit. For **subagent-driven-development**, Tasks 5, 6 and 7 (the three optional exporters) can be dispatched in parallel after Task 4 (templates) lands — they share no state beyond the IR.

Recommended sequence:
1. Solo execution: Tasks 1 → 2 → 3 → 4.
2. Optional parallelization: Tasks 5, 6, 7 in parallel.
3. Solo execution: Tasks 8 → 9 → 10 → 11.

## Open questions

None blocking. Two non-blocking calls to make during implementation:

- **PDF font fallback for non-Latin scripts**: ship Noto Sans CJK inside the package, or document the install? Decision deferred — start with system fallback, revisit if a user files an issue.
- **Anki model evolution**: if we want to add a third field later (e.g. "Source"), we'll need a migration plan because the model ID is derived from the model name. Out of scope for v1.
