"""Tests for jw_rag.chunkers.markers — multilingual continuation/closure catalog."""

from __future__ import annotations

import pytest

from jw_rag.chunkers.markers import (
    MarkerSet,
    detect_language,
    is_closure_start,
    is_continuation_start,
    load_markers,
)


def test_load_markers_returns_all_supported_languages() -> None:
    catalog = load_markers()
    assert "es" in catalog
    assert "en" in catalog
    assert "pt" in catalog


def test_marker_set_has_continuation_and_closure() -> None:
    catalog = load_markers()
    es = catalog["es"]
    assert isinstance(es, MarkerSet)
    assert "Sin embargo" in es.continuation
    assert "Por lo tanto" in es.closure


def test_marker_set_english_examples() -> None:
    catalog = load_markers()
    en = catalog["en"]
    assert "However" in en.continuation
    assert "Therefore" in en.closure


def test_marker_set_portuguese_examples() -> None:
    catalog = load_markers()
    pt = catalog["pt"]
    assert "No entanto" in pt.continuation
    assert "Portanto" in pt.closure


@pytest.mark.parametrize(
    ("paragraph", "lang", "expected"),
    [
        ("Sin embargo, hay que considerar...", "es", True),
        ("Por otro lado, la Biblia enseña...", "es", True),
        ("Esto no empieza con marcador.", "es", False),
        ("However, the scripture says...", "en", True),
        ("In contrast it claims...", "en", False),
        ("No entanto, devemos refletir.", "pt", True),
    ],
)
def test_is_continuation_start(paragraph: str, lang: str, expected: bool) -> None:
    assert is_continuation_start(paragraph, lang) is expected


@pytest.mark.parametrize(
    ("paragraph", "lang", "expected"),
    [
        ("Por lo tanto, la conclusión es...", "es", True),
        ("En conclusión, el versículo dice...", "es", True),
        ("Por lo tanto no aparece al inicio? Por lo tanto sí.", "es", True),
        ("Therefore the apostle concludes...", "en", True),
        ("Portanto, é assim.", "pt", True),
    ],
)
def test_is_closure_start(paragraph: str, lang: str, expected: bool) -> None:
    assert is_closure_start(paragraph, lang) is expected


def test_continuation_is_case_sensitive_at_start() -> None:
    assert is_continuation_start("sin embargo dentro de la frase.", "es") is False


def test_unknown_language_returns_false() -> None:
    assert is_continuation_start("Whatever", "qq") is False
    assert is_closure_start("Whatever", "qq") is False


def test_detect_language_es() -> None:
    text = "El amor es paciente. Por lo tanto el cristiano debe perdonar."
    assert detect_language(text) == "es"


def test_detect_language_en() -> None:
    text = "Love is patient and kind. The fruit of the spirit is mentioned in this verse."
    assert detect_language(text) == "en"


def test_detect_language_pt() -> None:
    text = "O amor é paciente. Portanto o cristão deve perdoar."
    assert detect_language(text) == "pt"


def test_detect_language_unknown_returns_none() -> None:
    assert detect_language("...") is None
