"""Quote extractor tests (Fase 70)."""

from __future__ import annotations

from jw_core.verification.image_quote.extractor import (
    detect_language,
    extract_quote,
)


def test_detect_language_es() -> None:
    assert (
        detect_language(
            "El amor de Jehová es para todos los que confían en él."
        )
        == "es"
    )


def test_detect_language_en() -> None:
    assert (
        detect_language(
            "Jehovah loves those that come to him with faith."
        )
        == "en"
    )


def test_detect_language_pt() -> None:
    assert (
        detect_language(
            "O amor de Jeová é para todos os que confiam nele segundo a Bíblia."
        )
        == "pt"
    )


def test_detect_language_unknown_on_empty() -> None:
    assert detect_language("") == "unknown"


def test_extract_quote_detects_wol_attribution() -> None:
    text = (
        "Que el amor a Jehová guíe nuestras decisiones.\n\n"
        "https://wol.jw.org/es/wol/d/r4/lp-s/1101989101"
    )
    q = extract_quote(text)
    assert q.has_attribution is True
    assert "wol.jw.org" in q.attribution_text
    assert "Que el amor" in q.cleaned_quote


def test_extract_quote_detects_pub_code_attribution() -> None:
    text = "Que el amor guíe.\n\nw23.04 p. 12"
    q = extract_quote(text)
    assert q.has_attribution is True
    assert "w23" in q.attribution_text.lower()


def test_extract_quote_no_attribution() -> None:
    q = extract_quote("Some random plain text with no citations.")
    assert q.has_attribution is False
    assert q.attribution_text == ""


def test_extract_quote_picks_longest_non_attribution_block() -> None:
    text = (
        "w23.04\n\n"
        "El reino de Dios es un gobierno real con Cristo Jesús como rey, "
        "fundado en Daniel 2:44.\n\n"
        "Más info"
    )
    q = extract_quote(text)
    assert "reino de Dios" in q.cleaned_quote
    assert q.has_attribution is True


def test_extract_quote_round_trip_models() -> None:
    q = extract_quote("Como dice Jehová que somos sus testigos.")
    dumped = q.model_dump()
    assert dumped["language_detected"] in ("es", "unknown")
