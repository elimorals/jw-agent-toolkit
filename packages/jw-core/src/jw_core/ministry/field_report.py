"""Local-first monthly field-service report for pioneers.

Stores ``HoursEntry`` and ``StudyEntry`` rows in SQLite, encrypts PII
columns at rest via :class:`jw_core.privacy.encryption.FieldEncryptor`,
and aggregates a :class:`MonthlyReport` for a given ``YYYY-MM``.

Read-only revisit counts come from an injectable ``RevisitProvider`` —
this module **never** imports ``jw_agents``.
"""

from __future__ import annotations

import os
import sqlite3
import time
import uuid
from datetime import date as _date
from pathlib import Path
from typing import Literal, Protocol

from pydantic import BaseModel, Field

from jw_core.privacy.encryption import FieldEncryptor

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


def _default_db_path() -> Path:
    return Path(os.getenv("JW_FIELD_DB", "~/.jw-agent-toolkit/field_service.db")).expanduser()


def _iso(d: _date) -> str:
    return d.isoformat()


def _from_iso(s: str | None) -> _date | None:
    return _date.fromisoformat(s) if s else None


class FieldReportStore:
    """SQLite-backed store for hours + studies + meetings.

    Encryption is automatic when ``JW_PRIVACY_KEY`` is set. Columns
    ``note`` and ``student_id`` go through the encryptor; everything
    else stays in cleartext so SQL aggregates (`SUM`, `GROUP BY`) work.
    """

    SCHEMA = """
    CREATE TABLE IF NOT EXISTS hours_entries (
        entry_id TEXT PRIMARY KEY,
        date TEXT NOT NULL,                -- ISO yyyy-mm-dd
        hours_decimal REAL NOT NULL,
        tag TEXT,
        note TEXT NOT NULL DEFAULT '',
        created_at_unix REAL NOT NULL
    );
    CREATE INDEX IF NOT EXISTS idx_hours_date ON hours_entries (date);

    CREATE TABLE IF NOT EXISTS studies (
        study_id TEXT PRIMARY KEY,
        student_id TEXT NOT NULL,          -- ciphered alias
        started_at TEXT NOT NULL,
        closed_at TEXT,
        note TEXT NOT NULL DEFAULT '',
        created_at_unix REAL NOT NULL
    );
    CREATE INDEX IF NOT EXISTS idx_studies_started ON studies (started_at);

    CREATE TABLE IF NOT EXISTS studies_meetings (
        study_id TEXT NOT NULL,
        met_date TEXT NOT NULL,
        PRIMARY KEY (study_id, met_date),
        FOREIGN KEY (study_id) REFERENCES studies(study_id) ON DELETE CASCADE
    );
    """

    def __init__(
        self,
        path: Path | str | None = None,
        *,
        encryptor: FieldEncryptor | None = None,
    ) -> None:
        self.path = Path(path).expanduser() if path else _default_db_path()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.path)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.executescript(self.SCHEMA)
        self._conn.commit()
        self._enc = encryptor if encryptor is not None else FieldEncryptor()

    # ----------------------------- hours ---------------------------------

    def add_hours(self, entry: HoursEntry) -> HoursEntry:
        if not entry.entry_id:
            entry.entry_id = uuid.uuid4().hex
        if not entry.created_at_unix:
            entry.created_at_unix = time.time()
        self._conn.execute(
            "INSERT INTO hours_entries "
            "(entry_id, date, hours_decimal, tag, note, created_at_unix) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                entry.entry_id,
                _iso(entry.date),
                float(entry.hours_decimal),
                entry.tag,
                self._enc.encrypt(entry.note) if entry.note else "",
                entry.created_at_unix,
            ),
        )
        self._conn.commit()
        return entry

    def list_hours(self, *, month: str | None = None) -> list[HoursEntry]:
        if month:
            cur = self._conn.execute(
                "SELECT * FROM hours_entries WHERE substr(date, 1, 7) = ? ORDER BY date",
                (month,),
            )
        else:
            cur = self._conn.execute("SELECT * FROM hours_entries ORDER BY date")
        return [self._row_to_hours(r) for r in cur.fetchall()]

    def _row_to_hours(self, row: sqlite3.Row) -> HoursEntry:
        note_raw = row["note"]
        return HoursEntry(
            entry_id=row["entry_id"],
            date=_date.fromisoformat(row["date"]),
            hours_decimal=row["hours_decimal"],
            tag=row["tag"],
            note=self._enc.decrypt(note_raw) if (self._enc.enabled and note_raw) else note_raw or "",
            created_at_unix=row["created_at_unix"],
        )

    # ---------------------------- studies --------------------------------

    def upsert_study(self, study: StudyEntry) -> StudyEntry:
        if not study.study_id:
            study.study_id = uuid.uuid4().hex
        if not study.created_at_unix:
            study.created_at_unix = time.time()
        self._conn.execute(
            "INSERT OR REPLACE INTO studies "
            "(study_id, student_id, started_at, closed_at, note, created_at_unix) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                study.study_id,
                self._enc.encrypt(study.student_id),
                _iso(study.started_at),
                _iso(study.closed_at) if study.closed_at else None,
                self._enc.encrypt(study.note) if study.note else "",
                study.created_at_unix,
            ),
        )
        self._conn.commit()
        return study

    def close_study(self, *, student_id: str, closed_at: _date) -> int:
        """Close every open study matching `student_id`. Returns rows updated."""

        # When encryption is on, student_id stored as ciphertext differs each call → scan.
        if self._enc.enabled:
            ids_to_close = [
                row["study_id"]
                for row in self._conn.execute(
                    "SELECT study_id, student_id FROM studies WHERE closed_at IS NULL"
                )
                if self._enc.decrypt(row["student_id"]) == student_id
            ]
            self._conn.executemany(
                "UPDATE studies SET closed_at = ? WHERE study_id = ?",
                [(_iso(closed_at), sid) for sid in ids_to_close],
            )
            self._conn.commit()
            return len(ids_to_close)
        cur = self._conn.execute(
            "UPDATE studies SET closed_at = ? "
            "WHERE student_id = ? AND closed_at IS NULL",
            (_iso(closed_at), student_id),
        )
        self._conn.commit()
        return cur.rowcount

    def mark_met(self, *, student_id: str, met_date: _date) -> None:
        # Resolve student alias → study_id(s)
        if self._enc.enabled:
            study_ids = [
                row["study_id"]
                for row in self._conn.execute("SELECT study_id, student_id FROM studies")
                if self._enc.decrypt(row["student_id"]) == student_id
            ]
        else:
            study_ids = [
                row["study_id"]
                for row in self._conn.execute(
                    "SELECT study_id FROM studies WHERE student_id = ?", (student_id,)
                )
            ]
        for sid in study_ids:
            self._conn.execute(
                "INSERT OR IGNORE INTO studies_meetings (study_id, met_date) VALUES (?, ?)",
                (sid, _iso(met_date)),
            )
        self._conn.commit()

    def list_studies(self) -> list[StudyEntry]:
        rows = self._conn.execute("SELECT * FROM studies ORDER BY started_at").fetchall()
        result: list[StudyEntry] = []
        for row in rows:
            mets = self._conn.execute(
                "SELECT met_date FROM studies_meetings WHERE study_id = ? ORDER BY met_date",
                (row["study_id"],),
            ).fetchall()
            result.append(
                StudyEntry(
                    study_id=row["study_id"],
                    student_id=self._enc.decrypt(row["student_id"])
                    if self._enc.enabled
                    else row["student_id"],
                    started_at=_date.fromisoformat(row["started_at"]),
                    closed_at=_from_iso(row["closed_at"]),
                    met_dates=[_date.fromisoformat(m["met_date"]) for m in mets],
                    note=self._enc.decrypt(row["note"])
                    if (self._enc.enabled and row["note"])
                    else row["note"] or "",
                    created_at_unix=row["created_at_unix"],
                )
            )
        return result

    # -------------------------- lifecycle --------------------------------

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> "FieldReportStore":
        return self

    def __exit__(self, *args: object) -> None:
        self.close()


import calendar
from decimal import ROUND_HALF_UP, Decimal


def _format_hours_5min(hours: float) -> str:
    """Render decimal hours as ``Xh Ymin`` rounded to 5-minute increments."""

    total_min = Decimal(str(hours)) * Decimal(60)
    rounded_5 = (total_min / Decimal(5)).quantize(Decimal("1"), rounding=ROUND_HALF_UP) * Decimal(5)
    h, m = divmod(int(rounded_5), 60)
    return f"{h}h {m:02d}min"


def _month_bounds(month: str) -> tuple[_date, _date]:
    """Return (start, end_inclusive) for ``YYYY-MM``."""

    y, m = month.split("-")
    yi, mi = int(y), int(m)
    last = calendar.monthrange(yi, mi)[1]
    return _date(yi, mi, 1), _date(yi, mi, last)


def _is_active_during(study: StudyEntry, start: _date, end: _date) -> bool:
    if study.started_at > end:
        return False
    if study.closed_at is not None and study.closed_at <= start:
        return False
    return True


def aggregate_monthly_report(
    store: FieldReportStore,
    month: str,
    *,
    revisits: RevisitProvider | None = None,
) -> MonthlyReport:
    """Aggregate every signal for ``month`` (YYYY-MM) into a :class:`MonthlyReport`.

    Active studies use the MAX during the month (per modern JW practice — see
    spec §"Decisiones clave"). ``revisits`` is optional; if omitted, the count
    falls back to ``0``.
    """

    month_start, month_end = _month_bounds(month)
    entries = store.list_hours(month=month)

    total = sum(e.hours_decimal for e in entries)
    breakdown: dict[str, float] = {}
    for e in entries:
        key = e.tag or "untagged"
        breakdown[key] = breakdown.get(key, 0.0) + e.hours_decimal

    days_with_service = len({e.date for e in entries})

    studies = store.list_studies()
    active = [s for s in studies if _is_active_during(s, month_start, month_end)]
    active_ids = [s.study_id for s in active]

    revisits_count = 0
    if revisits is not None:
        try:
            revisits_count = int(revisits.count_in_range(month_start, month_end))
        except Exception:  # noqa: BLE001 — provider never crashes the report
            revisits_count = 0

    return MonthlyReport(
        month=month,
        total_hours=round(float(total), 4),
        total_hours_display=_format_hours_5min(float(total)),
        breakdown_by_tag=breakdown,
        active_studies_max=len(active),
        active_studies_ids=active_ids,
        revisits_count=revisits_count,
        entries_count=len(entries),
        days_with_service=days_with_service,
    )
