"""F54.6 — tests for the ministry.MonthlyReport ↔ organized-app S-21 bridge."""

from __future__ import annotations

from jw_core.ministry.field_report import MonthlyReport
from jw_core.ministry.organized_bridge import (
    from_organized_monthly_report,
    to_organized_monthly_report,
)


def _sample_report() -> MonthlyReport:
    return MonthlyReport(
        month="2026-05",
        total_hours=12.0,
        total_hours_display="12.0",
        breakdown_by_tag={"ministry": 12.0},
        active_studies_max=3,
        active_studies_ids=["uid-a", "uid-b", "uid-c"],
        revisits_count=4,
        entries_count=5,
        days_with_service=4,
    )


def test_to_organized_pioneer_ships_hours() -> None:
    out = to_organized_monthly_report(_sample_report(), pioneer=True, person_uid="me")
    assert out.report_date == "2026-05"
    assert out.report_data.hours.field_service.monthly == "12"
    assert out.report_data.bible_studies.monthly == 3
    assert out.report_data.bible_studies.records == ["uid-a", "uid-b", "uid-c"]
    assert out.report_data.person_uid == "me"
    assert out.report_data.status == "pending"


def test_to_organized_publisher_hides_hours() -> None:
    """Post-2023 S-21: non-pioneers report 0 hours, just bible studies."""
    out = to_organized_monthly_report(_sample_report(), pioneer=False)
    assert out.report_data.hours.field_service.monthly == "0"
    assert out.report_data.bible_studies.monthly == 3


def test_to_organized_shared_ministry_flag() -> None:
    out = to_organized_monthly_report(_sample_report(), shared_ministry=True)
    assert out.report_data.shared_ministry is True


def test_to_organized_status_override() -> None:
    out = to_organized_monthly_report(_sample_report(), status="submitted")
    assert out.report_data.status == "submitted"


def test_from_organized_round_trips_basic_fields() -> None:
    original = _sample_report()
    organized = to_organized_monthly_report(original, pioneer=True)
    back = from_organized_monthly_report(organized)
    assert back.month == original.month
    assert back.total_hours == original.total_hours
    assert back.active_studies_max == original.active_studies_max
    assert back.active_studies_ids == original.active_studies_ids
