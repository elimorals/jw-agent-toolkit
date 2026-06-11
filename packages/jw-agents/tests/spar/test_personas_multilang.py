"""Multi-language persona loader tests (Fase 66 post-MVP)."""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from jw_agents.spar.personas import get_persona, list_personas
from jw_agents.spar.personas.loader import clear_persona_cache


@pytest.fixture(autouse=True)
def _clean(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.delenv("JW_SPAR_PERSONA_DIR", raising=False)
    clear_persona_cache()
    yield
    clear_persona_cache()


def test_get_persona_returns_es_default_when_no_lang() -> None:
    p = get_persona("catholic")
    assert p.language == "es"
    assert p.display_name.startswith("María")


def test_get_persona_returns_en_variant() -> None:
    p = get_persona("catholic", language="en")
    assert p.language == "en"
    assert p.display_name.startswith("Mary")


def test_get_persona_returns_pt_variant() -> None:
    p = get_persona("catholic", language="pt")
    assert p.language == "pt"
    # Brazilian Portuguese for Mary
    assert p.display_name.startswith("Maria")


def test_get_persona_falls_back_to_default_when_lang_missing() -> None:
    # `language="fr"` has no variant for any builtin -> falls back to default
    p = get_persona("atheist", language="fr")
    assert p.language == "es"


def test_list_personas_es_default_returns_six() -> None:
    keys = {p.key for p in list_personas()}
    assert keys == {
        "catholic",
        "evangelical",
        "atheist",
        "muslim",
        "nominal",
        "young_skeptic",
    }


def test_list_personas_en_overlay_returns_en_variants() -> None:
    personas = list_personas(language="en")
    keys = {p.key for p in personas}
    assert keys == {
        "catholic",
        "evangelical",
        "atheist",
        "muslim",
        "nominal",
        "young_skeptic",
    }
    catholic = next(p for p in personas if p.key == "catholic")
    assert catholic.language == "en"


def test_list_personas_pt_overlay_returns_pt_variants() -> None:
    personas = list_personas(language="pt")
    catholic = next(p for p in personas if p.key == "catholic")
    assert catholic.language == "pt"
