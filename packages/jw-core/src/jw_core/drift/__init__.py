"""jw_core.drift - diachronic doctrinal-drift analyzer (Fase 72).

Public API:
    from jw_core.drift import (
        Era, Citation, EraSnapshot, DriftEvent, DoctrinalDrift,
        analyze_doctrinal_drift,
    )
"""

from __future__ import annotations

from jw_core.drift.models import (
    Citation,
    DoctrinalDrift,
    DriftEvent,
    Era,
    EraSnapshot,
)

__all__ = [
    "Citation",
    "DoctrinalDrift",
    "DriftEvent",
    "Era",
    "EraSnapshot",
]
