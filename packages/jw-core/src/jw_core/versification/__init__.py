"""Canonical-versification subpackage (Fase 46).

Public API:

    from jw_core.versification import (
        Tradition,
        VerseCoord,
        VersificationMapping,
        MappingResult,
        to_canonical,
        explain,
        load_catalog,
    )

The module does NO I/O at import time. The catalog JSON is loaded lazily
on first call via `@functools.lru_cache(maxsize=1)`.

This subpackage MUST NOT import from jw_rag, jw_agents, or jw_mcp. It
depends only on jw_core.models and reads jw_core.data.
"""

from jw_core.versification.explain import explain
from jw_core.versification.mapping import to_canonical
from jw_core.versification.models import (
    MappingResult,
    Tradition,
    VerseCoord,
    VersificationMapping,
)
from jw_core.versification.registry import catalog_version, load_catalog

__all__ = [
    "MappingResult",
    "Tradition",
    "VerseCoord",
    "VersificationMapping",
    "catalog_version",
    "explain",
    "load_catalog",
    "to_canonical",
]
