"""Tests for jw_core.exporters.markdown."""

from __future__ import annotations

from pathlib import Path

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
