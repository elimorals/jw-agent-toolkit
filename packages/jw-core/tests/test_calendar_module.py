"""Tests for the calendar module (Module 6)."""

from __future__ import annotations

import tempfile
from datetime import date, timedelta
from pathlib import Path

from jw_core.calendar.events import Event, EventStore, upcoming_for_user
from jw_core.calendar.memorial import (
    MEMORIAL_DATES,
    countdown_to_memorial,
    memorial_date_for_year,
    memorial_preparation_checklist,
)
from jw_core.calendar.visit import circuit_overseer_checklist, elder_visit_checklist


def _tmp_db() -> Path:
    return Path(tempfile.mkdtemp()) / "calendar.db"


# ── Memorial ─────────────────────────────────────────────────────────────


def test_memorial_published_table_loaded() -> None:
    md = memorial_date_for_year(2026)
    assert md.source == "published"
    assert md.iso_date == MEMORIAL_DATES[2026]


def test_memorial_estimate_falls_back() -> None:
    md = memorial_date_for_year(2099)
    assert md.source == "estimated"
    assert md.warning


def test_countdown_returns_positive_days() -> None:
    today = date(2026, 1, 1)
    info = countdown_to_memorial(today=today)
    assert info["memorial_iso"] == MEMORIAL_DATES[2026]
    assert info["days_remaining"] > 0


def test_countdown_rolls_over_after_memorial() -> None:
    today = date(2026, 12, 1)
    info = countdown_to_memorial(today=today)
    # Memorial 2026 already passed → next is 2027
    assert info["memorial_iso"] == MEMORIAL_DATES[2027]


def test_preparation_checklist_localized() -> None:
    items_es = memorial_preparation_checklist("es")
    items_en = memorial_preparation_checklist("en")
    assert items_es[0]["task"] != items_en[0]["task"]
    assert all("id" in it and "task" in it for it in items_es)


# ── Events store ─────────────────────────────────────────────────────────


def test_event_store_upsert_and_upcoming() -> None:
    path = _tmp_db()
    today = date.today()
    with EventStore(path) as store:
        store.upsert(
            Event(
                kind="circuit",
                title="Circuit Overseer Visit",
                start_iso=(today + timedelta(days=5)).isoformat(),
                location="Salón del Reino A",
            )
        )
        store.upsert(
            Event(
                kind="custom",
                title="Past event",
                start_iso=(today - timedelta(days=10)).isoformat(),
            )
        )
        upcoming = store.upcoming(from_date=today.isoformat())
    titles = {e.title for e in upcoming}
    assert "Circuit Overseer Visit" in titles
    assert "Past event" not in titles


def test_upcoming_for_user_horizon() -> None:
    path = _tmp_db()
    today = date.today()
    with EventStore(path) as store:
        store.upsert(Event(title="Inside", start_iso=(today + timedelta(days=10)).isoformat()))
        store.upsert(Event(title="Beyond", start_iso=(today + timedelta(days=120)).isoformat()))
        items = upcoming_for_user(horizon_days=30, today=today, store=store)
    assert any(e.title == "Inside" for e in items)
    assert all(e.title != "Beyond" for e in items)


def test_event_store_delete_returns_bool() -> None:
    path = _tmp_db()
    with EventStore(path) as store:
        ev = store.upsert(Event(title="X", start_iso="2026-06-01"))
        assert store.delete(ev.event_id)
        assert not store.delete(ev.event_id)


# ── Visit checklists ────────────────────────────────────────────────────


def test_circuit_overseer_checklist_has_items() -> None:
    items_en = circuit_overseer_checklist("en")
    assert len(items_en) >= 5
    assert all("task" in it for it in items_en)


def test_elder_visit_checklist_localizes() -> None:
    items_en = elder_visit_checklist("en")
    items_pt = elder_visit_checklist("pt")
    assert items_en[0]["task"] != items_pt[0]["task"]
