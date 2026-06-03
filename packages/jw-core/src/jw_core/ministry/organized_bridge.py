"""F54.6 — bridge between `ministry.field_report.MonthlyReport` and the
organized-app schema (`UserFieldServiceMonthlyReportType`).

`MonthlyReport` is the aggregate the toolkit's local SQLite store produces.
`UserFieldServiceMonthlyReportType` is the post-2023 S-21 layout
organized-app uses (the modern report: hours only if pioneer, bible studies
count, shared_ministry, pending/submitted/confirmed status).

Why we keep both:
  - `MonthlyReport` is an in-memory aggregate keyed by the toolkit's
    SQLite tables — no `_deleted` / `updatedAt` envelopes, no
    person_uid, no shared_ministry. It's the right shape for CLI output.
  - `UserFieldServiceMonthlyReportType` is the wire format for sync with
    organized-app PWA. It demands the CRDT envelopes and status enum.

The bridge converts one to the other without duplicating the SQLite store.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from jw_core.ministry.field_report import MonthlyReport
from jw_core.models_organized.field_service_report import (
    MonthlyBibleStudies,
    MonthlyHours,
    MonthlyHoursSplit,
    UserFieldServiceMonthlyReportData,
    UserFieldServiceMonthlyReportType,
)


def to_organized_monthly_report(
    report: MonthlyReport,
    *,
    person_uid: str | None = None,
    shared_ministry: bool = False,
    status: Literal["pending", "submitted", "confirmed"] = "pending",
    pioneer: bool = False,
    comments: str = "",
) -> UserFieldServiceMonthlyReportType:
    """Convert a `MonthlyReport` to the organized-app S-21 shape.

    `pioneer=True` ships hours in `field_service`; non-pioneers leave them
    at "0" (post-2023 publishers only report bible studies + did-something).
    `report.active_studies_max` becomes the monthly bible studies count.
    """
    now_iso = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    hours_str = _format_hours(report.total_hours) if pioneer else "0"
    return UserFieldServiceMonthlyReportType(
        report_date=report.month,
        report_data=UserFieldServiceMonthlyReportData(
            deleted=False,
            updatedAt=now_iso,
            shared_ministry=shared_ministry,
            hours=MonthlyHours(
                field_service=MonthlyHoursSplit(daily="0", monthly=hours_str),
                credit=MonthlyHoursSplit(daily="0", monthly="0"),
            ),
            bible_studies=MonthlyBibleStudies(
                daily=0,
                monthly=report.active_studies_max,
                records=report.active_studies_ids,
            ),
            comments=comments,
            record_type="monthly",
            status=status,
            person_uid=person_uid,
        ),
    )


def from_organized_monthly_report(report: UserFieldServiceMonthlyReportType) -> MonthlyReport:
    """Convert the organized-app S-21 shape back to a `MonthlyReport` aggregate.

    Loses some fidelity (no `breakdown_by_tag`, `revisits_count`, etc. —
    those are local-only). Returns a `MonthlyReport` populated with what
    organized-app actually tracks.
    """
    data = report.report_data
    try:
        total = float(data.hours.field_service.monthly or "0")
    except ValueError:
        total = 0.0
    return MonthlyReport(
        month=report.report_date,
        total_hours=total,
        total_hours_display=data.hours.field_service.monthly or "0",
        breakdown_by_tag={},
        active_studies_max=data.bible_studies.monthly,
        active_studies_ids=list(data.bible_studies.records),
        revisits_count=0,
        entries_count=0,
        days_with_service=0,
    )


def _format_hours(hours: float) -> str:
    """JW reports hours as integer strings (post-2023 S-21)."""
    return str(int(round(hours)))
