"""Citation integrity validator — verifies wol URLs and MEPS mappings.

Public API:
    from jw_core.citations import (
        CitationValidator,
        CitationCheck,
        CitationReport,
        ResolveStatus,
        CatalogStatus,
        DriftStatus,
    )

See `docs/guias/citation-validator.md` and Fase 23 spec.
"""

from jw_core.citations.models import (
    CatalogStatus,
    CitationCheck,
    CitationReport,
    DriftStatus,
    ResolveStatus,
)
try:
    from jw_core.citations.validator import CitationValidator
except ImportError:  # built incrementally; full class lands in Task 4
    CitationValidator = None  # type: ignore[assignment, misc]

__all__ = [
    "CatalogStatus",
    "CitationCheck",
    "CitationReport",
    "CitationValidator",
    "DriftStatus",
    "ResolveStatus",
]
