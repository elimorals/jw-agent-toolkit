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


@pytest.mark.skipif(
    not WEASY_AVAILABLE,
    reason="weasyprint not installed (install jw-core[pdf])",
)
def test_export_pdf_writes_valid_file(tmp_path: Path) -> None:
    from jw_core.exporters.pdf import export_pdf

    out = tmp_path / "demo.pdf"
    written = export_pdf(_sheet(), out=out)
    assert written == out
    assert out.exists()
    head = out.read_bytes()[:4]
    assert head == b"%PDF"


@pytest.mark.skipif(
    not WEASY_AVAILABLE,
    reason="weasyprint not installed (install jw-core[pdf])",
)
def test_export_pdf_study_sheet_theme(tmp_path: Path) -> None:
    from jw_core.exporters.pdf import export_pdf

    out = tmp_path / "demo.pdf"
    export_pdf(_sheet(), out=out, theme="study-sheet")
    assert out.read_bytes()[:4] == b"%PDF"


@pytest.mark.skipif(
    not WEASY_AVAILABLE,
    reason="weasyprint not installed (install jw-core[pdf])",
)
def test_export_pdf_creates_parent_dirs(tmp_path: Path) -> None:
    from jw_core.exporters.pdf import export_pdf

    out = tmp_path / "deep" / "nested" / "demo.pdf"
    export_pdf(_sheet(), out=out)
    assert out.exists()


@pytest.mark.skipif(
    not WEASY_AVAILABLE,
    reason="weasyprint not installed (install jw-core[pdf])",
)
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
