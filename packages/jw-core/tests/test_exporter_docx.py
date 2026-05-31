"""Tests for jw_core.exporters.docx."""

from __future__ import annotations

import importlib.util
import zipfile
from pathlib import Path

import pytest
from jw_core.exporters.errors import MissingDependencyError
from jw_core.exporters.ir import CitationIR, StudySection, StudySheet

DOCX_AVAILABLE = importlib.util.find_spec("docx") is not None


def _sheet() -> StudySheet:
    return StudySheet(
        title="Trinidad",
        subtitle="Análisis",
        sections=[
            StudySection(
                heading="Jehová es uno",
                body="La Biblia es clara.",
                excerpt="Deut 6:4",
                citations=[CitationIR(url="https://wol.jw.org/x", short_label="Folleto Trinidad")],
            )
        ],
        footer_note="Generado por jw-agent-toolkit.",
    )


@pytest.mark.skipif(
    not DOCX_AVAILABLE,
    reason="python-docx not installed (install jw-core[docx])",
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


@pytest.mark.skipif(
    not DOCX_AVAILABLE,
    reason="python-docx not installed (install jw-core[docx])",
)
def test_export_docx_contains_title_and_heading(tmp_path: Path) -> None:
    from jw_core.exporters.docx import export_docx

    out = tmp_path / "demo.docx"
    export_docx(_sheet(), out=out)
    with zipfile.ZipFile(out) as zf:
        xml = zf.read("word/document.xml").decode("utf-8")
    assert "Trinidad" in xml
    assert "Jehová es uno" in xml


@pytest.mark.skipif(
    not DOCX_AVAILABLE,
    reason="python-docx not installed (install jw-core[docx])",
)
def test_export_docx_includes_citation_hyperlink(tmp_path: Path) -> None:
    from jw_core.exporters.docx import export_docx

    out = tmp_path / "demo.docx"
    export_docx(_sheet(), out=out)
    with zipfile.ZipFile(out) as zf:
        rels = zf.read("word/_rels/document.xml.rels").decode("utf-8")
    assert "wol.jw.org" in rels


@pytest.mark.skipif(
    not DOCX_AVAILABLE,
    reason="python-docx not installed (install jw-core[docx])",
)
def test_export_docx_creates_parent_dirs(tmp_path: Path) -> None:
    from jw_core.exporters.docx import export_docx

    out = tmp_path / "deep" / "x.docx"
    export_docx(_sheet(), out=out)
    assert out.exists()


def test_missing_dependency_when_pythondocx_absent(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
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
