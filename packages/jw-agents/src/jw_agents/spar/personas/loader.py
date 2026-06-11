"""Persona loader: reads TOML files in this directory and returns Persona objects.

Honors `JW_SPAR_PERSONA_DIR` env override: if set, reads from that
directory instead of the builtin path.

Naming convention:
  - `<key>.toml`           : language-default persona (typically `es`).
  - `<key>_<lang>.toml`    : explicit per-language variant.

`get_persona(key, language=None)` resolution order:
  1. `<key>_<language>.toml` if `language` is provided.
  2. `<key>.toml` (default variant).
  3. `PersonaNotFound`.
"""

from __future__ import annotations

import os
import tomllib
from functools import lru_cache
from pathlib import Path

from jw_agents.spar.models import Persona

_HERE = Path(__file__).parent
_VALID_LANG_SUFFIXES = ("en", "es", "pt")


class PersonaNotFound(KeyError):
    """Raised when `get_persona(key, language)` cannot resolve a persona."""


def _persona_dir() -> Path:
    override = os.environ.get("JW_SPAR_PERSONA_DIR")
    if override:
        return Path(override).expanduser()
    return _HERE


def _read_persona_file(path: Path) -> Persona:
    with path.open("rb") as f:
        data = tomllib.load(f)
    return Persona(**data)


@lru_cache
def _load_all() -> dict[tuple[str, str | None], Persona]:
    """Map (key, lang_suffix) -> Persona.

    `lang_suffix` is None for `<key>.toml` (default variant) and a lang
    code for `<key>_<lang>.toml`.
    """
    out: dict[tuple[str, str | None], Persona] = {}
    pdir = _persona_dir()
    if not pdir.exists():
        return out
    for toml_path in sorted(pdir.glob("*.toml")):
        try:
            persona = _read_persona_file(toml_path)
        except Exception:
            continue
        stem = toml_path.stem
        if "_" in stem:
            base_key, _, lang = stem.rpartition("_")
            if lang in _VALID_LANG_SUFFIXES:
                out[(base_key, lang)] = persona
                continue
        out[(persona.key, None)] = persona
    return out


def clear_persona_cache() -> None:
    """Reset cache (tests / env overrides)."""
    _load_all.cache_clear()


def list_personas(language: str | None = None) -> list[Persona]:
    """All personas, optionally filtered by language variant.

    With `language=None`: one Persona per key (default variant).
    With `language="<lang>"`: the language variant overlays the default
    when both exist.
    """
    all_personas = _load_all()
    out: dict[str, Persona] = {}
    for (key, lang), persona in all_personas.items():
        if lang is None:
            out[key] = persona
    if language is not None:
        for (key, lang), persona in all_personas.items():
            if lang == language:
                out[key] = persona
    return sorted(out.values(), key=lambda p: p.key)


def get_persona(key: str, language: str | None = None) -> Persona:
    """Return one persona by key. Raises `PersonaNotFound` if absent."""
    personas = _load_all()
    if language is not None:
        variant = personas.get((key, language))
        if variant is not None:
            return variant
    default = personas.get((key, None))
    if default is None:
        raise PersonaNotFound(key)
    return default
