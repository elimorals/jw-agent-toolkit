"""Tests for the synth validators."""

from __future__ import annotations

from jw_finetune.synth import validators


def test_bible_ref_es() -> None:
    assert validators.is_valid_bible_ref("Génesis 1:1")
    assert validators.is_valid_bible_ref("Mateo 24:14")
    assert validators.is_valid_bible_ref("1 Corintios 13:4-7")
    assert validators.is_valid_bible_ref("2 Pedro 3:13")


def test_bible_ref_no_match() -> None:
    assert not validators.is_valid_bible_ref("hola mundo")
    assert not validators.is_valid_bible_ref("xyz 99")
    assert not validators.is_valid_bible_ref("")


def test_count_bible_refs() -> None:
    txt = "Como dice Mateo 24:14 y Hechos 1:8, debemos predicar."
    assert validators.count_bible_refs(txt) >= 2


def test_length_ok_accepts_reasonable() -> None:
    assert validators.length_ok(
        "¿Qué es el Reino?",
        "El Reino es el gobierno celestial de Dios mencionado en Daniel 2:44.",
    )


def test_length_ok_rejects_too_short() -> None:
    assert not validators.length_ok("", "ok")
    assert not validators.length_ok("A?", "x")


def test_length_ok_rejects_too_long() -> None:
    long_q = "x" * 500
    long_a = "y" * 3000
    assert not validators.length_ok(long_q, "respuesta corta razonable aquí.")
    assert not validators.length_ok("pregunta razonable?", long_a)


def test_lang_matches_no_langdetect_passes(monkeypatch) -> None:
    """If langdetect isn't installed, the validator defaults to pass."""
    monkeypatch.setattr(validators, "_HAS_LANGDETECT", False)
    assert validators.lang_matches("Hello world", "es") is True
