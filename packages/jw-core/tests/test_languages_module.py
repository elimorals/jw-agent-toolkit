"""Tests for the expanded language registry + translation hooks (Module 8)."""

from __future__ import annotations

from jw_core.languages import SIGN_LANGUAGES, all_languages, get_language
from jw_core.translation import mask_references, render_reference, restore_references


# ── Registry ────────────────────────────────────────────────────────────


def test_tier1_languages_all_registered() -> None:
    keys = {l.iso for l in all_languages()}
    assert {"en", "es", "pt", "fr", "de", "it", "ru", "ja", "ko", "zh"} <= keys


def test_french_resolution_by_iso_and_jw_code() -> None:
    fr_iso = get_language("fr")
    fr_jw = get_language("F")
    assert fr_iso.iso == fr_jw.iso == "fr"


def test_sign_languages_carry_broadcasting_root() -> None:
    assert "ase" in SIGN_LANGUAGES and SIGN_LANGUAGES["ase"]["broadcasting_root"].endswith("/videos/")


# ── Translation helpers ─────────────────────────────────────────────────


def test_mask_and_restore_roundtrip_en_to_es() -> None:
    text = "Read John 3:16 and Romans 12:2 carefully."
    masked = mask_references(text)
    assert "<<REF:" in masked.text
    assert len(masked.references) == 2
    out = restore_references(masked.text, masked.references, target_language="es")
    assert "Juan" in out
    assert "Romanos" in out


def test_mask_keeps_non_reference_text_intact() -> None:
    text = "Hello world without any reference."
    masked = mask_references(text)
    assert masked.text == text
    assert masked.references == []


def test_render_reference_with_range() -> None:
    out = render_reference(book_num=43, chapter=3, verse_start=16, verse_end=18, language="es")
    assert out == "Juan 3:16-18"


def test_render_reference_falls_back_to_english_for_unknown_lang() -> None:
    out = render_reference(book_num=1, chapter=1, verse_start=1, language="zz")
    assert "Genesis" in out or "Génesis" in out  # falls to English


def test_mask_preserves_order_in_output() -> None:
    text = "Cite first Genesis 1:1 then Revelation 22:13."
    masked = mask_references(text)
    en = restore_references(masked.text, masked.references, target_language="en")
    # First reference should appear first.
    assert en.find("Genesis") < en.find("Revelation")
