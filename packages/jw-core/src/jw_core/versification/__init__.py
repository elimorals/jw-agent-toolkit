"""Canonical-versification subpackage (Fase 46).

Public API grows as later tasks land. After T1 only the Pydantic models are
exported; T3 adds load_catalog, T5 adds to_canonical, T8 adds explain.

This subpackage MUST NOT import from jw_rag, jw_agents, or jw_mcp. It
depends only on jw_core.models and reads jw_core.data.
"""

from jw_core.versification.models import (
    MappingResult,
    Tradition,
    VerseCoord,
    VersificationMapping,
)

__all__ = [
    "MappingResult",
    "Tradition",
    "VerseCoord",
    "VersificationMapping",
]
