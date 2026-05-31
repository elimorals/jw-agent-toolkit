"""Local SQLite store of items the news monitor has already reported.

Schema:
    news_seen(channel, item_id, first_seen_at, last_seen_at, metadata_json)
    news_runs(id=1, last_run_at)

Both timestamps are stored as ISO-8601 UTC strings.

Default path: ~/.jw-agent-toolkit/news_seen.db (env: JW_NEWS_SEEN_DB).
"""

from __future__ import annotations

import json
import os
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path

from jw_core.news.models import NewsItem, SeenRecord

_SCHEMA = """
CREATE TABLE IF NOT EXISTS news_seen (
    channel TEXT NOT NULL,
    item_id TEXT NOT NULL,
    first_seen_at TEXT NOT NULL,
    last_seen_at TEXT NOT NULL,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    PRIMARY KEY (channel, item_id)
);
CREATE INDEX IF NOT EXISTS idx_news_seen_last_seen ON news_seen(last_seen_at);

CREATE TABLE IF NOT EXISTS news_runs (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    last_run_at TEXT NOT NULL
);
"""


def _default_path() -> Path:
    env = os.getenv("JW_NEWS_SEEN_DB")
    if env:
        return Path(env).expanduser()
    return Path("~/.jw-agent-toolkit/news_seen.db").expanduser()


def _iso(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat()


def _from_iso(s: str) -> datetime:
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


class SeenStore:
    """Tiny SQLite store of (channel, item_id) sightings + last_run."""

    def __init__(self, path: Path | str | None = None) -> None:
        self.path = Path(path).expanduser() if path else _default_path()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(
            self.path,
            isolation_level=None,
            check_same_thread=False,
        )
        self._lock = threading.Lock()
        with self._lock:
            self._conn.executescript(_SCHEMA)
            self._conn.execute("PRAGMA journal_mode=WAL")

    def is_seen(self, channel: str, item_id: str) -> bool:
        with self._lock:
            row = self._conn.execute(
                "SELECT 1 FROM news_seen WHERE channel = ? AND item_id = ?",
                (channel, item_id),
            ).fetchone()
        return row is not None

    def mark_seen(self, item: NewsItem, *, now: datetime | None = None) -> None:
        ts = _iso(now or datetime.now(timezone.utc))
        metadata = json.dumps(
            item.metadata or {}, separators=(",", ":"), sort_keys=True
        )
        with self._lock:
            existing = self._conn.execute(
                "SELECT first_seen_at FROM news_seen WHERE channel = ? AND item_id = ?",
                (item.channel, item.item_id),
            ).fetchone()
            first_seen = existing[0] if existing else ts
            self._conn.execute(
                "INSERT OR REPLACE INTO news_seen "
                "(channel, item_id, first_seen_at, last_seen_at, metadata_json) "
                "VALUES (?, ?, ?, ?, ?)",
                (item.channel, item.item_id, first_seen, ts, metadata),
            )

    def all_seen(self, channel: str | None = None) -> list[SeenRecord]:
        sql = "SELECT channel, item_id, first_seen_at, last_seen_at, metadata_json FROM news_seen"
        params: tuple = ()
        if channel is not None:
            sql += " WHERE channel = ?"
            params = (channel,)
        sql += " ORDER BY channel, item_id"
        with self._lock:
            rows = self._conn.execute(sql, params).fetchall()
        return [
            SeenRecord(
                channel=r[0],
                item_id=r[1],
                first_seen_at=_from_iso(r[2]),
                last_seen_at=_from_iso(r[3]),
                metadata=json.loads(r[4] or "{}"),
            )
            for r in rows
        ]

    def last_run_at(self) -> datetime | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT last_run_at FROM news_runs WHERE id = 1"
            ).fetchone()
        return _from_iso(row[0]) if row else None

    def set_last_run_at(self, when: datetime) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT OR REPLACE INTO news_runs (id, last_run_at) VALUES (1, ?)",
                (_iso(when),),
            )

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    def __enter__(self) -> SeenStore:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()
