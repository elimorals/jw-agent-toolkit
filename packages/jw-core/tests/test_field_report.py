"""Tests for jw_core.ministry.field_report and related field_service modules."""

from __future__ import annotations

import json
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Task 1 — vocabulary
# ---------------------------------------------------------------------------


def test_default_tags_present() -> None:
    from jw_core.data.field_service_tags import DEFAULT_TAGS, load_tags

    assert "street" in DEFAULT_TAGS
    assert "return_visit" in DEFAULT_TAGS
    assert "bible_study" in DEFAULT_TAGS
    tags = load_tags(override_path=None)
    assert set(DEFAULT_TAGS).issubset(tags)


def test_override_adds_local_tag(tmp_path: Path) -> None:
    from jw_core.data.field_service_tags import load_tags

    override = tmp_path / "field_service_tags_local.json"
    override.write_text(json.dumps({"add": ["hospital"], "remove": []}), encoding="utf-8")
    tags = load_tags(override_path=override)
    assert "hospital" in tags
    assert "street" in tags  # defaults survive


def test_override_can_remove(tmp_path: Path) -> None:
    from jw_core.data.field_service_tags import load_tags

    override = tmp_path / "field_service_tags_local.json"
    override.write_text(json.dumps({"add": [], "remove": ["letter"]}), encoding="utf-8")
    tags = load_tags(override_path=override)
    assert "letter" not in tags
    assert "street" in tags


def test_override_missing_file_returns_defaults(tmp_path: Path) -> None:
    from jw_core.data.field_service_tags import DEFAULT_TAGS, load_tags

    assert set(load_tags(override_path=tmp_path / "nope.json")) == set(DEFAULT_TAGS)


# ---------------------------------------------------------------------------
# Task 2 — models
# ---------------------------------------------------------------------------


def test_hours_entry_validates() -> None:
    from datetime import date as date_
    from jw_core.ministry.field_report import HoursEntry

    e = HoursEntry(
        entry_id="abc",
        date=date_(2026, 5, 15),
        hours_decimal=2.5,
        tag="street",
        note="parque central",
    )
    assert e.hours_decimal == 2.5
    assert e.tag == "street"


def test_hours_entry_rejects_overflow() -> None:
    from datetime import date as date_
    from jw_core.ministry.field_report import HoursEntry

    with pytest.raises(ValueError):
        HoursEntry(entry_id="x", date=date_(2026, 5, 15), hours_decimal=25.0)


def test_hours_entry_rejects_unknown_tag() -> None:
    from datetime import date as date_
    from jw_core.ministry.field_report import HoursEntry

    with pytest.raises(ValueError):
        HoursEntry(
            entry_id="x", date=date_(2026, 5, 15), hours_decimal=1.0, tag="weird"  # type: ignore[arg-type]
        )


def test_study_entry_defaults() -> None:
    from datetime import date as date_
    from jw_core.ministry.field_report import StudyEntry

    s = StudyEntry(study_id="s1", student_id="maria", started_at=date_(2026, 4, 1))
    assert s.closed_at is None
    assert s.met_dates == []
    assert s.note == ""


def test_monthly_report_shape() -> None:
    from jw_core.ministry.field_report import MonthlyReport

    r = MonthlyReport(
        month="2026-05",
        total_hours=10.5,
        total_hours_display="10h 30min",
        breakdown_by_tag={"street": 5.0, "untagged": 5.5},
        active_studies_max=3,
        active_studies_ids=["s1", "s2", "s3"],
        revisits_count=7,
        entries_count=4,
        days_with_service=3,
    )
    assert r.month == "2026-05"
    assert r.active_studies_max == 3
