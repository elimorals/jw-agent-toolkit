"""Builtin persona definitions (TOML) + loader."""

from __future__ import annotations

from jw_agents.spar.personas.loader import (
    PersonaNotFound,
    get_persona,
    list_personas,
)

__all__ = ["PersonaNotFound", "get_persona", "list_personas"]
