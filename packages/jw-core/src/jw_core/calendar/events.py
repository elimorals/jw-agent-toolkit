"""Generic event store for assemblies, circuit visits, conventions, memorials.

Local-only SQLite at `~/.jw-agent-toolkit/calendar.db` (override
`JW_CALENDAR_DB`).

VISION.md: "Asambleas regionales/circuito: detección automática de
fechas + materiales relacionados".

Detection isn't actually automatic yet — JW doesn't expose a public API
for individual congregation events. The user records the event manually;
the toolkit handles reminders, prep checklists, and (Phase 16+) URL
matching against jw.org/eventos.
"""

from __future__ import annotations

import os
import sqlite3
import time
import uuid
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path


def _default_db_path() -> Path:
    return Path(os.getenv("JW_CALENDAR_DB", "~/.jw-agent-toolkit/calendar.db")).expanduser()


@dataclass
class Event:
    event_id: str = ""
    kind: str = "memorial"  # memorial | assembly | circuit | convention | elder_visit | custom
    title: str = ""
    start_iso: str = ""
    end_iso: str = ""
    location: str = ""
    language: str = "en"
    notes: str = ""
    tags: list[str] = field(default_factory=list)
    created_at_unix: float = 0.0

    def ensure_id(self) -> None:
        if not self.event_id:
            self.event_id = uuid.uuid4().hex


class EventStore:
    SCHEMA = """
    CREATE TABLE IF NOT EXISTS events (
        event_id TEXT PRIMARY KEY,
        kind TEXT NOT NULL,
        title TEXT NOT NULL,
        start_iso TEXT NOT NULL,
        end_iso TEXT NOT NULL DEFAULT '',
        location TEXT NOT NULL DEFAULT '',
        language TEXT NOT NULL DEFAULT 'en',
        notes TEXT NOT NULL DEFAULT '',
        tags TEXT NOT NULL DEFAULT '',
        created_at_unix REAL NOT NULL
    );
    CREATE INDEX IF NOT EXISTS idx_start ON events (start_iso);
    CREATE INDEX IF NOT EXISTS idx_kind ON events (kind);
    """

    def __init__(self, db_path: Path | str | None = None) -> None:
        self.path = Path(db_path).expanduser() if db_path else _default_db_path()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.path)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(self.SCHEMA)
        self._conn.commit()

    def upsert(self, event: Event) -> Event:
        event.ensure_id()
        if not event.created_at_unix:
            event.created_at_unix = time.time()
        self._conn.execute(
            "INSERT OR REPLACE INTO events "
            "(event_id, kind, title, start_iso, end_iso, location, language, "
            "notes, tags, created_at_unix) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                event.event_id,
                event.kind,
                event.title,
                event.start_iso,
                event.end_iso,
                event.location,
                event.language,
                event.notes,
                ",".join(event.tags),
                event.created_at_unix,
            ),
        )
        self._conn.commit()
        return event

    def get(self, event_id: str) -> Event | None:
        row = self._conn.execute("SELECT * FROM events WHERE event_id = ?", (event_id,)).fetchone()
        return _row_to_event(row) if row else None

    def list_all(self, *, kind: str | None = None) -> list[Event]:
        if kind:
            cur = self._conn.execute("SELECT * FROM events WHERE kind = ? ORDER BY start_iso", (kind,))
        else:
            cur = self._conn.execute("SELECT * FROM events ORDER BY start_iso")
        return [_row_to_event(r) for r in cur.fetchall()]

    def upcoming(self, *, from_date: str | None = None, kind: str | None = None) -> list[Event]:
        if from_date is None:
            from_date = date.today().isoformat()
        params: list[object] = [from_date]
        sql = "SELECT * FROM events WHERE start_iso >= ? "
        if kind:
            sql += "AND kind = ? "
            params.append(kind)
        sql += "ORDER BY start_iso"
        return [_row_to_event(r) for r in self._conn.execute(sql, params).fetchall()]

    def delete(self, event_id: str) -> bool:
        cur = self._conn.execute("DELETE FROM events WHERE event_id = ?", (event_id,))
        self._conn.commit()
        return cur.rowcount > 0

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> EventStore:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()


def _row_to_event(row: sqlite3.Row) -> Event:
    return Event(
        event_id=row["event_id"],
        kind=row["kind"],
        title=row["title"],
        start_iso=row["start_iso"],
        end_iso=row["end_iso"],
        location=row["location"],
        language=row["language"],
        notes=row["notes"],
        tags=row["tags"].split(",") if row["tags"] else [],
        created_at_unix=row["created_at_unix"],
    )


def upcoming_for_user(
    *,
    horizon_days: int = 90,
    today: date | None = None,
    store: EventStore | None = None,
) -> list[Event]:
    """Convenience: events whose start_iso falls within `horizon_days`."""
    from datetime import timedelta

    today = today or date.today()
    cutoff = (today + timedelta(days=horizon_days)).isoformat()
    owned = store is None
    store = store or EventStore()
    try:
        candidates = store.upcoming(from_date=today.isoformat())
    finally:
        if owned:
            store.close()
    return [e for e in candidates if e.start_iso and e.start_iso <= cutoff]
