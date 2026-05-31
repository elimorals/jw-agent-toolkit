"""Tests for letter / phone / cart templates and topic-family resolver."""

from __future__ import annotations

import pytest

from jw_core.data.letter_templates import (
    AUDIENCES,
    TOPIC_FAMILIES,
    LetterTemplate,
    get_template,
    list_audiences,
    list_topic_families,
    resolve_topic_family,
)


def test_letter_template_dataclass_minimal() -> None:
    t = LetterTemplate(
        opener={"en": "Hi.", "es": "Hola.", "pt": "Olá."},
        bridge={"en": "Bridge.", "es": "Puente.", "pt": "Ponte."},
        closing={"en": "Bye.", "es": "Adiós.", "pt": "Tchau."},
        suggested_scripture="John 3:16",
        suggested_jw_link="https://www.jw.org/",
    )
    assert t.opener["es"] == "Hola."
    assert t.time_target_seconds == 0
    assert t.word_count_target == 150


def test_resolve_topic_family_keyword_match_es() -> None:
    assert resolve_topic_family("perdí a mi esposo", "es") == "family"
    assert resolve_topic_family("tengo mucha ansiedad", "es") == "peace"
    assert resolve_topic_family("¿existe esperanza?", "es") == "hope"
    assert resolve_topic_family("vicio del alcohol", "es") == "addictions"


def test_resolve_topic_family_keyword_match_en() -> None:
    assert resolve_topic_family("my marriage is failing", "en") == "family"
    assert resolve_topic_family("design in the universe", "en") == "science"


def test_resolve_topic_family_fallback_to_generic() -> None:
    assert resolve_topic_family("totally unrelated text", "es") == "generic"
    assert resolve_topic_family("", "es") == "generic"


def test_resolve_topic_family_unknown_language_falls_back_to_en() -> None:
    # Unknown lang code → use English keyword map.
    assert resolve_topic_family("hope for the future", "xx") == "hope"


def test_resolve_topic_family_case_insensitive() -> None:
    assert resolve_topic_family("ESPERANZA Y PAZ", "es") in {"hope", "peace"}


def test_get_template_returns_specific_when_present() -> None:
    t = get_template("grieving", "suffering")
    assert isinstance(t, LetterTemplate)
    # Opener must mention the audience-specific tone keyword:
    assert "duelo" in t.opener["es"].lower() or "pérdida" in t.opener["es"].lower()


def test_get_template_falls_back_to_audience_generic() -> None:
    # An audience exists but no specific family → audience generic.
    t = get_template("young", "addictions")
    assert isinstance(t, LetterTemplate)


def test_get_template_falls_back_to_default_generic() -> None:
    # Bad audience → default generic.
    t = get_template("nonexistent_audience", "nonexistent_family")
    assert isinstance(t, LetterTemplate)


def test_every_audience_has_a_generic_template() -> None:
    for aud in AUDIENCES:
        t = get_template(aud, "generic")
        assert isinstance(t, LetterTemplate), aud
        for lang in ("en", "es", "pt"):
            assert t.opener.get(lang), f"{aud} missing opener[{lang}]"
            assert t.bridge.get(lang), f"{aud} missing bridge[{lang}]"
            assert t.closing.get(lang), f"{aud} missing closing[{lang}]"


def test_list_audiences_includes_default_first() -> None:
    auds = list_audiences()
    assert auds[0] == "default"
    assert set(auds) == set(AUDIENCES)


def test_list_topic_families_covers_8_documented() -> None:
    fams = set(list_topic_families())
    assert {
        "family", "suffering", "hope", "science",
        "peace", "identity", "addictions", "generic",
    } <= fams


from jw_core.data.phone_templates import (
    PHONE_TEMPLATES,
    get_phone_template,
)


def test_phone_template_has_time_target_75s() -> None:
    t = get_phone_template("default", "generic")
    assert t.time_target_seconds == 75
    assert t.word_count_target == 0


def test_phone_every_audience_has_generic() -> None:
    from jw_core.data.letter_templates import AUDIENCES

    for aud in AUDIENCES:
        t = get_phone_template(aud, "generic")
        for lang in ("en", "es", "pt"):
            assert t.opener.get(lang)
            assert t.bridge.get(lang)
            assert t.closing.get(lang)


def test_phone_fallback_chain() -> None:
    t = get_phone_template("nonexistent", "nonexistent")
    assert t is PHONE_TEMPLATES[("default", "generic")]
