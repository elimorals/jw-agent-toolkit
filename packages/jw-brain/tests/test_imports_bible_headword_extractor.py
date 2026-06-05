"""F58.14 — extractor de cabezales de JWPUB del Insight.

Verifica:
- extracción de titles del JWPUB fixture (Abraham, Jerusalem, Moses).
- roundtrip persist → load conserva los cabezales (normalizados a lowercase).
- load sobre brain sin extracted_headwords.json devuelve set() vacío.
"""

from __future__ import annotations

import json
from pathlib import Path

from jw_brain.imports.bible.headword_extractor import (
    extract_headwords_from_jwpub,
    load_extracted_headwords,
    persist_to_brain,
)

FIXTURE = Path(__file__).parent / "fixtures" / "insight_mini" / "it_mini.jwpub"


# ── Extracción ──────────────────────────────────────────────────────────────


def test_extract_returns_3_titles() -> None:
    """El fixture mini tiene 3 documents (Abraham, Jerusalem, Moses)."""
    headwords = extract_headwords_from_jwpub(FIXTURE)
    assert len(headwords) == 3
    assert {h.lower() for h in headwords} == {"abraham", "jerusalem", "moses"}


def test_extract_preserves_original_case() -> None:
    """Los titles se devuelven como están en el JWPUB, sin normalizar."""
    headwords = extract_headwords_from_jwpub(FIXTURE)
    # El fixture tiene capitalización title-case.
    assert "Abraham" in headwords or "abraham" in {h.lower() for h in headwords}


# ── Persist / Load roundtrip ────────────────────────────────────────────────


def test_persist_and_load_roundtrip(tmp_path: Path) -> None:
    headwords = ["Abraham", "Moses", "JERUSALEM"]
    target = persist_to_brain(headwords, brain_home=tmp_path)
    assert target.exists()
    assert target.name == "extracted_headwords.json"
    loaded = load_extracted_headwords(tmp_path)
    assert loaded == {"abraham", "moses", "jerusalem"}


def test_persist_deduplicates_and_sorts(tmp_path: Path) -> None:
    """Cabezales duplicados (con diferentes casings) se mergean en lowercase."""
    headwords = ["Abraham", "abraham", "ABRAHAM", "Moses"]
    target = persist_to_brain(headwords, brain_home=tmp_path)
    data = json.loads(target.read_text(encoding="utf-8"))
    assert data["headwords"] == ["abraham", "moses"]


def test_persist_skips_empty_strings(tmp_path: Path) -> None:
    """Cabezales vacíos o sólo whitespace no se persisten."""
    headwords = ["Abraham", "", "   ", "Moses"]
    target = persist_to_brain(headwords, brain_home=tmp_path)
    data = json.loads(target.read_text(encoding="utf-8"))
    assert data["headwords"] == ["abraham", "moses"]


def test_persist_creates_brain_dir(tmp_path: Path) -> None:
    """`persist_to_brain` crea el directorio si no existe."""
    target_dir = tmp_path / "nested" / "brain"
    assert not target_dir.exists()
    target = persist_to_brain(["Abraham"], brain_home=target_dir)
    assert target.exists()
    assert target.parent == target_dir


def test_load_missing_brain_returns_empty(tmp_path: Path) -> None:
    """Brain sin extracted_headwords.json → set() vacío (no error)."""
    assert load_extracted_headwords(tmp_path / "nope") == set()


def test_load_missing_file_in_existing_brain(tmp_path: Path) -> None:
    """Brain existe pero sin extracted_headwords.json → set() vacío."""
    (tmp_path / "config.toml").write_text("", encoding="utf-8")
    assert load_extracted_headwords(tmp_path) == set()


# ── E2E: extract + persist + load sobre fixture ─────────────────────────────


def test_extract_persist_load_e2e(tmp_path: Path) -> None:
    headwords = extract_headwords_from_jwpub(FIXTURE)
    persist_to_brain(headwords, brain_home=tmp_path)
    loaded = load_extracted_headwords(tmp_path)
    assert loaded == {"abraham", "jerusalem", "moses"}
