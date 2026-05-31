"""Local-first monthly field-service report for pioneers.

Stores ``HoursEntry`` and ``StudyEntry`` rows in SQLite, encrypts PII
columns at rest via :class:`jw_core.privacy.encryption.FieldEncryptor`,
and aggregates a :class:`MonthlyReport` for a given ``YYYY-MM``.

Read-only revisit counts come from an injectable ``RevisitProvider`` —
this module **never** imports ``jw_agents``.
"""

from __future__ import annotations

from datetime import date as _date
from typing import Literal, Protocol

from pydantic import BaseModel, Field

# Frozen at import time. Override-aware variant lives behind a CLI helper.
ServiceTag = Literal[
    "street",
    "return_visit",
    "bible_study",
    "online",
    "phone",
    "cart",
    "letter",
    "other",
]


class HoursEntry(BaseModel):
    """One log of hours worked."""

    entry_id: str
    date: _date
    hours_decimal: float = Field(ge=0.0, le=24.0)
    tag: ServiceTag | None = None
    note: str = ""
    created_at_unix: float = 0.0


class StudyEntry(BaseModel):
    """One active or closed Bible study."""

    study_id: str
    student_id: str  # arbitrary alias chosen by the user; ciphered at rest
    started_at: _date
    closed_at: _date | None = None
    met_dates: list[_date] = Field(default_factory=list)
    note: str = ""
    created_at_unix: float = 0.0


class MonthlyReport(BaseModel):
    """Aggregate report shape returned to CLI/MCP/exporters."""

    month: str  # "YYYY-MM"
    total_hours: float
    total_hours_display: str
    breakdown_by_tag: dict[str, float]
    active_studies_max: int
    active_studies_ids: list[str]
    revisits_count: int
    entries_count: int
    days_with_service: int


class RevisitProvider(Protocol):
    """Read-only count of revisits in a half-open date range [start, end]."""

    def count_in_range(self, start: _date, end: _date) -> int: ...


# Forward declarations; implementations land in later tasks.
class FieldReportStore:  # pragma: no cover - placeholder until Task 3
    """SQLite-backed store. Implemented in Task 3."""


def aggregate_monthly_report(  # pragma: no cover - placeholder until Task 5
    store: "FieldReportStore", month: str, *, revisits: RevisitProvider | None = None
) -> MonthlyReport:
    """Aggregator. Implemented in Task 5."""

    raise NotImplementedError
