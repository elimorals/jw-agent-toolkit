"""F58.7 — Parser Insight clasifica cabezales como persona/lugar.

El parser opera sobre un `JwpubMetadata` ya descifrado por
`jw_core.parsers.jwpub.parse_jwpub`. Reusa el flujo de descifrado existente
(no toca jwpub.py) y proyecta cada documento JWPUB a un `InsightEntry`
solo cuando el headword cae en el catálogo de personas o lugares.

Las clasificaciones se hacen por **título del documento** (no por
meps_document_id, que varía entre formulas de publicación).
"""

from __future__ import annotations

from pathlib import Path

from jw_brain.imports.bible.models import InsightEntry
from jw_brain.imports.bible.parser_insight import (
    PERSON_HEADWORDS,
    PLACE_HEADWORDS,
    InsightParser,
    classify_entry_kind,
)
from jw_core.parsers.jwpub import parse_jwpub

FIXTURE = Path(__file__).parent / "fixtures" / "insight_mini" / "it_mini.jwpub"


# ── classify_entry_kind ─────────────────────────────────────────────────


def test_classify_entry_kind_abraham_is_person() -> None:
    assert classify_entry_kind("Abraham") == "person"
    # Robusto a punctuación/whitespace al final.
    assert classify_entry_kind("  Abraham.  ") == "person"
    assert classify_entry_kind("ABRAHAM") == "person"
    assert "abraham" in PERSON_HEADWORDS


def test_classify_entry_kind_jerusalem_is_place() -> None:
    assert classify_entry_kind("Jerusalem") == "place"
    assert classify_entry_kind("jerusalem,") == "place"
    assert "jerusalem" in PLACE_HEADWORDS


def test_classify_entry_kind_unknown_returns_none() -> None:
    # Headwords que no son ni persona ni lugar (e.g. conceptos teológicos)
    # se descartan: el parser no las emite.
    assert classify_entry_kind("Atonement") is None
    assert classify_entry_kind("Ransom") is None
    assert classify_entry_kind("") is None


# ── InsightParser sobre fixture real ────────────────────────────────────


def test_parser_extracts_abraham_entry() -> None:
    metadata = parse_jwpub(FIXTURE)
    parser = InsightParser(symbol="it", meps_language=0)
    entries = list(parser.iter_entries(metadata))

    abraham = next((e for e in entries if e.headword == "Abraham"), None)
    assert abraham is not None, f"Abraham not found in {[e.headword for e in entries]}"
    assert isinstance(abraham, InsightEntry)
    assert abraham.kind == "person"
    assert abraham.symbol == "it"
    assert abraham.meps_language == 0
    assert abraham.document_id == 12000001
    assert abraham.first_mention_raw == "Gen. 11:26"
    assert "1/11" in abraham.first_mention_href
    # Excerpt no incluye markup XHTML.
    assert "<" not in abraham.text_excerpt
    assert "Abraham" in abraham.text_excerpt


def test_parser_extracts_jerusalem_as_place() -> None:
    metadata = parse_jwpub(FIXTURE)
    parser = InsightParser(symbol="it", meps_language=0)
    entries = list(parser.iter_entries(metadata))

    jerusalem = next((e for e in entries if e.headword == "Jerusalem"), None)
    assert jerusalem is not None
    assert jerusalem.kind == "place"
    assert jerusalem.first_mention_raw == "2 Sam. 5:6"
    assert jerusalem.document_id == 12000002


def test_parser_skips_unclassified_entries() -> None:
    """El fixture solo contiene Abraham/Jerusalem/Moses; todos clasifican.
    Sin embargo, el parser debe filtrar cualquier doc sin título o cuyo
    título caiga fuera del catálogo. Verificamos contando solo entradas
    clasificadas."""
    metadata = parse_jwpub(FIXTURE)
    parser = InsightParser(symbol="it", meps_language=0)
    entries = list(parser.iter_entries(metadata))

    # Las 3 del fixture: Abraham (person), Jerusalem (place), Moses (person).
    assert len(entries) == 3
    headwords = {e.headword for e in entries}
    assert headwords == {"Abraham", "Jerusalem", "Moses"}
    # Y todas las emitidas tienen `kind` válido (nunca None).
    assert all(e.kind in ("person", "place") for e in entries)
