"""Tests for i18n loader."""

from __future__ import annotations

import pytest

from create_jw_agent.i18n import (
    DEFAULT_LANG,
    SUPPORTED,
    detect_lang,
    translator,
)


def test_supported_languages() -> None:
    assert SUPPORTED == ("en", "es", "pt")


def test_detect_lang_from_lc_all(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LC_ALL", "es_ES.UTF-8")
    monkeypatch.delenv("LANG", raising=False)
    assert detect_lang() == "es"


def test_detect_lang_from_lang(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LC_ALL", raising=False)
    monkeypatch.setenv("LANG", "pt_BR.UTF-8")
    assert detect_lang() == "pt"


def test_detect_lang_unknown_falls_back_to_en(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LC_ALL", "ja_JP.UTF-8")
    monkeypatch.delenv("LANG", raising=False)
    assert detect_lang() == DEFAULT_LANG


def test_detect_lang_empty_env_falls_back(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LC_ALL", raising=False)
    monkeypatch.delenv("LANG", raising=False)
    assert detect_lang() == DEFAULT_LANG


def test_translator_returns_translated_string() -> None:
    t = translator("es")
    assert "testigos de Jehov" in t("tagline")


def test_translator_falls_back_to_en_for_missing_key() -> None:
    t = translator("es")
    # Unknown key → returns key itself
    out = t("missing.key.xyz")
    assert out == "missing.key.xyz"


def test_translator_formats_kwargs() -> None:
    t = translator("en")
    out = t("render.created", n=12, path="/tmp/foo")
    assert "12" in out
    assert "/tmp/foo" in out


def test_translator_unknown_lang_defaults_to_en() -> None:
    t = translator("xx")
    assert t.lang == DEFAULT_LANG


def test_all_three_languages_have_same_keys() -> None:
    import json
    from importlib.resources import files

    pkg = files("create_jw_agent.lang")
    en_keys = set(json.loads(pkg.joinpath("en.json").read_text(encoding="utf-8")).keys())
    es_keys = set(json.loads(pkg.joinpath("es.json").read_text(encoding="utf-8")).keys())
    pt_keys = set(json.loads(pkg.joinpath("pt.json").read_text(encoding="utf-8")).keys())
    assert en_keys == es_keys == pt_keys, (
        f"missing in es: {en_keys - es_keys}, "
        f"missing in pt: {en_keys - pt_keys}, "
        f"extra in es: {es_keys - en_keys}, "
        f"extra in pt: {pt_keys - en_keys}"
    )
