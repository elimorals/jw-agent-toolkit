"""Tests for the per-country locale context."""

from __future__ import annotations

import asyncio

from jw_core.data.locale_context import (
    LOCALE_CONTEXTS,
    context_for_presentation,
    get_locale,
    list_locales,
)


def test_catalog_has_15_plus_countries() -> None:
    assert len(LOCALE_CONTEXTS) >= 15


def test_get_locale_case_insensitive() -> None:
    a = get_locale("mx")
    b = get_locale("MX")
    assert a is b


def test_locale_japan_holds_sensitive_topics() -> None:
    ctx = get_locale("JP")
    assert ctx is not None
    assert "ancestral worship" in ctx.sensitive_topics


def test_list_locales_localized() -> None:
    items = list_locales("es")
    by_iso = {l["iso_3166"]: l["name"] for l in items}
    assert by_iso["MX"] == "México"
    assert by_iso["JP"] == "Japón"


def test_context_for_presentation_renders_dict() -> None:
    out = context_for_presentation("DE", display_language="es")
    assert "country" in out and out["country"] == "Alemania"
    assert "cultural_anchors" in out


def test_unknown_country_reports_error() -> None:
    out = context_for_presentation("XX")
    assert "error" in out


def test_presentation_builder_with_country() -> None:
    from jw_agents.presentation_builder import presentation_builder

    result = asyncio.run(presentation_builder("catholic", language="S", country="MX"))
    assert result.metadata["country"] == "MX"
    assert "cultural_anchors" in result.metadata["locale_context"]
    assert result.metadata["locale_context"]["country"] in {"México", "Mexico"}


def test_presentation_builder_invalid_country_warns() -> None:
    from jw_agents.presentation_builder import presentation_builder

    result = asyncio.run(presentation_builder("catholic", language="E", country="ZZ"))
    assert result.warnings
    assert result.metadata["locale_context"] == {}
