"""Tests for jw_core.exporters.anki."""

from __future__ import annotations

import importlib.util
import zipfile
from pathlib import Path

import pytest

from jw_core.exporters.errors import MissingDependencyError
from jw_core.exporters.ir import CitationIR, StudySection, StudySheet

ANKI_AVAILABLE = importlib.util.find_spec("genanki") is not None


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


@pytest.mark.skipif(
    not ANKI_AVAILABLE,
    reason="genanki not installed (install jw-core[anki])",
)
def test_export_apkg_writes_valid_zip(tmp_path: Path) -> None:
    from jw_core.exporters.anki import export_apkg

    out = tmp_path / "deck.apkg"
    written = export_apkg(_sheet(), out=out)
    assert written == out
    assert out.exists()
    assert zipfile.is_zipfile(out)


@pytest.mark.skipif(
    not ANKI_AVAILABLE,
    reason="genanki not installed (install jw-core[anki])",
)
def test_export_apkg_default_one_note_per_section(tmp_path: Path) -> None:
    from jw_core.exporters.anki import build_deck, export_apkg

    deck = build_deck(_sheet(), per_citation_cards=False)
    assert len(deck.notes) == 2  # one per section


@pytest.mark.skipif(
    not ANKI_AVAILABLE,
    reason="genanki not installed (install jw-core[anki])",
)
def test_export_apkg_per_citation_cards(tmp_path: Path) -> None:
    from jw_core.exporters.anki import build_deck

    deck = build_deck(_sheet(), per_citation_cards=True)
    # 2 section notes + 2 extra (citations of first section only — second section has 0)
    assert len(deck.notes) == 4


@pytest.mark.skipif(
    not ANKI_AVAILABLE,
    reason="genanki not installed (install jw-core[anki])",
)
def test_export_apkg_guid_stable_across_runs(tmp_path: Path) -> None:
    from jw_core.exporters.anki import build_deck

    d1 = build_deck(_sheet())
    d2 = build_deck(_sheet())
    g1 = sorted(n.guid for n in d1.notes)
    g2 = sorted(n.guid for n in d2.notes)
    assert g1 == g2


@pytest.mark.skipif(
    not ANKI_AVAILABLE,
    reason="genanki not installed (install jw-core[anki])",
)
def test_export_apkg_guid_changes_when_content_changes(tmp_path: Path) -> None:
    from jw_core.exporters.anki import build_deck

    d1 = build_deck(_sheet())
    sheet2 = _sheet()
    sheet2.sections[0].heading = "Otro encabezado"
    d2 = build_deck(sheet2)
    g1 = sorted(n.guid for n in d1.notes)
    g2 = sorted(n.guid for n in d2.notes)
    assert g1 != g2


@pytest.mark.skipif(
    not ANKI_AVAILABLE,
    reason="genanki not installed (install jw-core[anki])",
)
def test_export_apkg_deck_id_stable(tmp_path: Path) -> None:
    from jw_core.exporters.anki import build_deck

    d1 = build_deck(_sheet())
    d2 = build_deck(_sheet())
    assert d1.deck_id == d2.deck_id


@pytest.mark.skipif(
    not ANKI_AVAILABLE,
    reason="genanki not installed (install jw-core[anki])",
)
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
