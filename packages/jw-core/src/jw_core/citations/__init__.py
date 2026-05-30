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
from jw_core.citations.validator import (
    CitationValidator,
    FetcherResponse,
)

__all__ = [
    "CatalogStatus",
    "CitationCheck",
    "CitationReport",
    "CitationValidator",
    "DriftStatus",
    "FetcherResponse",
    "ResolveStatus",
]
