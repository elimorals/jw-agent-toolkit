"""Persona loader tests."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from jw_agents.spar.personas import (
    PersonaNotFound,
    get_persona,
    list_personas,
)
from jw_agents.spar.personas.loader import clear_persona_cache


@pytest.fixture(autouse=True)
def _clean(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.delenv("JW_SPAR_PERSONA_DIR", raising=False)
    clear_persona_cache()
    yield
    clear_persona_cache()


def test_list_personas_returns_six_builtins() -> None:
    personas = list_personas()
    keys = {p.key for p in personas}
    assert keys == {
        "catholic",
        "evangelical",
        "atheist",
        "muslim",
        "nominal",
        "young_skeptic",
    }


def test_get_persona_catholic_has_core_beliefs() -> None:
    p = get_persona("catholic")
    assert p.display_name.startswith("María")
    assert len(p.core_beliefs) >= 3
    assert len(p.typical_doubts) >= 3
    assert p.tone == "warm"


def test_get_persona_unknown_raises() -> None:
    with pytest.raises(PersonaNotFound):
        get_persona("zoroastrian")


def test_env_override_persona_dir(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    custom = tmp_path / "custom_persona.toml"
    custom.write_text(
        'key = "atheist"\n'
        'display_name = "Custom Ana"\n'
        'language = "es"\n'
        'tone = "skeptical"\n'
        'core_beliefs = ["x"]\n'
        'typical_doubts = ["y"]\n'
        'profile_md = "custom"\n'
    )
    monkeypatch.setenv("JW_SPAR_PERSONA_DIR", str(tmp_path))
    clear_persona_cache()
    p = get_persona("atheist")
    assert p.display_name == "Custom Ana"
