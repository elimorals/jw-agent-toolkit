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


# ---------------------------------------------------------------------------
# Task 3 — FieldReportStore CRUD
# ---------------------------------------------------------------------------


def _enc_off(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("JW_PRIVACY_KEY", raising=False)


def test_store_creates_db_and_inserts_hours(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from datetime import date as date_
    from jw_core.ministry.field_report import FieldReportStore, HoursEntry

    _enc_off(monkeypatch)
    db = tmp_path / "fs.db"
    store = FieldReportStore(path=db)
    e = store.add_hours(
        HoursEntry(entry_id="", date=date_(2026, 5, 15), hours_decimal=2.5, tag="street")
    )
    assert e.entry_id  # auto-assigned uuid
    assert db.exists()

    rows = store.list_hours(month="2026-05")
    assert len(rows) == 1
    assert rows[0].hours_decimal == 2.5
    assert rows[0].tag == "street"
    store.close()


def test_store_list_hours_filters_by_month(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from datetime import date as date_
    from jw_core.ministry.field_report import FieldReportStore, HoursEntry

    _enc_off(monkeypatch)
    store = FieldReportStore(path=tmp_path / "fs.db")
    store.add_hours(HoursEntry(entry_id="", date=date_(2026, 4, 30), hours_decimal=1.0))
    store.add_hours(HoursEntry(entry_id="", date=date_(2026, 5, 1), hours_decimal=2.0))
    store.add_hours(HoursEntry(entry_id="", date=date_(2026, 5, 31), hours_decimal=3.0))
    store.add_hours(HoursEntry(entry_id="", date=date_(2026, 6, 1), hours_decimal=4.0))

    may = store.list_hours(month="2026-05")
    assert sorted(r.hours_decimal for r in may) == [2.0, 3.0]
    store.close()


def test_store_log_study_and_close(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from datetime import date as date_
    from jw_core.ministry.field_report import FieldReportStore, StudyEntry

    _enc_off(monkeypatch)
    store = FieldReportStore(path=tmp_path / "fs.db")
    s = store.upsert_study(
        StudyEntry(study_id="", student_id="maria", started_at=date_(2026, 4, 1))
    )
    assert s.study_id
    store.close_study(student_id="maria", closed_at=date_(2026, 5, 10))
    studies = store.list_studies()
    assert studies[0].closed_at == date_(2026, 5, 10)


def test_store_mark_met_today(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from datetime import date as date_
    from jw_core.ministry.field_report import FieldReportStore, StudyEntry

    _enc_off(monkeypatch)
    store = FieldReportStore(path=tmp_path / "fs.db")
    store.upsert_study(StudyEntry(study_id="", student_id="maria", started_at=date_(2026, 5, 1)))
    store.mark_met(student_id="maria", met_date=date_(2026, 5, 5))
    store.mark_met(student_id="maria", met_date=date_(2026, 5, 12))
    store.mark_met(student_id="maria", met_date=date_(2026, 5, 5))  # duplicate must be a no-op
    studies = store.list_studies()
    assert sorted(studies[0].met_dates) == [date_(2026, 5, 5), date_(2026, 5, 12)]


def test_store_encrypts_note_when_key_set(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import sqlite3

    from cryptography.fernet import Fernet  # type: ignore[import-not-found]

    from datetime import date as date_
    from jw_core.ministry.field_report import FieldReportStore, HoursEntry

    monkeypatch.setenv("JW_PRIVACY_KEY", Fernet.generate_key().decode("ascii"))
    db = tmp_path / "fs.db"
    store = FieldReportStore(path=db)
    store.add_hours(
        HoursEntry(
            entry_id="",
            date=date_(2026, 5, 15),
            hours_decimal=2.5,
            tag="street",
            note="secret note",
        )
    )

    # Inspect raw row: note column must NOT contain "secret note" cleartext.
    raw = sqlite3.connect(db)
    raw.row_factory = sqlite3.Row
    row = raw.execute("SELECT note FROM hours_entries").fetchone()
    assert "secret note" not in row["note"]
    raw.close()

    # But round-trip via store decrypts correctly.
    entries = store.list_hours(month="2026-05")
    assert entries[0].note == "secret note"
    store.close()


# ---------------------------------------------------------------------------
# Task 4 — RevisitProvider
# ---------------------------------------------------------------------------


class _FakeRevisits:
    def __init__(self, by_month: dict[str, int]) -> None:
        self._by_month = by_month

    def count_in_range(self, start, end):  # type: ignore[no-untyped-def]
        from datetime import date as date_

        assert isinstance(start, date_) and isinstance(end, date_)
        return self._by_month.get(start.strftime("%Y-%m"), 0)


def test_revisit_provider_protocol_is_structural() -> None:
    from jw_core.ministry.field_report import RevisitProvider

    p: RevisitProvider = _FakeRevisits({"2026-05": 7})
    from datetime import date as date_

    assert p.count_in_range(date_(2026, 5, 1), date_(2026, 5, 31)) == 7


# ---------------------------------------------------------------------------
# Task 5 — aggregate_monthly_report
# ---------------------------------------------------------------------------


def _seed_may_2026(store) -> None:
    from datetime import date as date_
    from jw_core.ministry.field_report import HoursEntry, StudyEntry

    store.add_hours(HoursEntry(entry_id="", date=date_(2026, 5, 2), hours_decimal=2.0, tag="street"))
    store.add_hours(HoursEntry(entry_id="", date=date_(2026, 5, 2), hours_decimal=1.5, tag="return_visit"))
    store.add_hours(HoursEntry(entry_id="", date=date_(2026, 5, 10), hours_decimal=3.75, tag="cart"))
    store.add_hours(HoursEntry(entry_id="", date=date_(2026, 5, 20), hours_decimal=0.5, tag=None))
    # April leftover — must NOT count
    store.add_hours(HoursEntry(entry_id="", date=date_(2026, 4, 30), hours_decimal=10.0, tag="street"))

    # 4 studies: 1 already closed in April; 2 started before; 1 started mid-May; 1 closed mid-May
    store.upsert_study(
        StudyEntry(
            study_id="", student_id="alpha", started_at=date_(2026, 3, 1), closed_at=date_(2026, 4, 15)
        )
    )
    store.upsert_study(StudyEntry(study_id="", student_id="beta", started_at=date_(2026, 4, 1)))
    store.upsert_study(StudyEntry(study_id="", student_id="gamma", started_at=date_(2026, 4, 15)))
    store.upsert_study(StudyEntry(study_id="", student_id="delta", started_at=date_(2026, 5, 5)))
    store.upsert_study(
        StudyEntry(
            study_id="", student_id="epsilon", started_at=date_(2026, 4, 20), closed_at=date_(2026, 5, 12)
        )
    )


def test_aggregate_monthly_report_basic(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _enc_off(monkeypatch)
    from jw_core.ministry.field_report import FieldReportStore, aggregate_monthly_report

    store = FieldReportStore(path=tmp_path / "fs.db")
    _seed_may_2026(store)
    report = aggregate_monthly_report(
        store, "2026-05", revisits=_FakeRevisits({"2026-05": 11})
    )

    # 2.0 + 1.5 + 3.75 + 0.5 = 7.75 hours
    assert report.total_hours == pytest.approx(7.75)
    # 5-min rounding: 7h 45min
    assert report.total_hours_display == "7h 45min"
    assert report.breakdown_by_tag["street"] == pytest.approx(2.0)
    assert report.breakdown_by_tag["return_visit"] == pytest.approx(1.5)
    assert report.breakdown_by_tag["cart"] == pytest.approx(3.75)
    assert report.breakdown_by_tag["untagged"] == pytest.approx(0.5)
    assert report.entries_count == 4
    assert report.days_with_service == 3

    # Active in May: beta, gamma, delta, epsilon. alpha closed in April.
    assert report.active_studies_max == 4
    assert report.revisits_count == 11


def test_aggregate_monthly_report_5min_rounding_half_up() -> None:
    """7.46 hours → 7h 30min (rounds 27.6 → 30, since 27.6 is closer to 30 than 25 under 5-min rounding)."""

    from jw_core.ministry.field_report import _format_hours_5min

    assert _format_hours_5min(7.0) == "7h 00min"
    assert _format_hours_5min(7.5) == "7h 30min"
    assert _format_hours_5min(7.46) == "7h 30min"  # 27.6min → round to 30
    assert _format_hours_5min(0.0) == "0h 00min"
    assert _format_hours_5min(1.0833) == "1h 05min"  # 4.998 → 5


def test_aggregate_monthly_report_empty(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _enc_off(monkeypatch)
    from jw_core.ministry.field_report import FieldReportStore, aggregate_monthly_report

    store = FieldReportStore(path=tmp_path / "fs.db")
    r = aggregate_monthly_report(store, "2026-05", revisits=None)
    assert r.total_hours == 0.0
    assert r.entries_count == 0
    assert r.active_studies_max == 0
    assert r.revisits_count == 0
    assert r.days_with_service == 0
