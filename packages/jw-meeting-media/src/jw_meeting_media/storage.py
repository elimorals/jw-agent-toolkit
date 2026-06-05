"""Storage sqlite local para meetings y downloads.

Esquema:
    CREATE TABLE programs (
        language TEXT, year INT, week INT, kind TEXT,
        program_json TEXT NOT NULL,
        saved_at TEXT NOT NULL,
        PRIMARY KEY (language, year, week, kind)
    );

    CREATE TABLE downloads (
        ref_key TEXT PRIMARY KEY,   -- sha256 or url
        ref_url TEXT NOT NULL,
        local_path TEXT NOT NULL,
        sha256 TEXT,
        downloaded_at TEXT NOT NULL
    );
"""

from __future__ import annotations

import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

from jw_meeting_media.models import MediaRef, MeetingKind, MeetingProgram

_SCHEMA = """
CREATE TABLE IF NOT EXISTS programs (
    language TEXT NOT NULL,
    year INT NOT NULL,
    week INT NOT NULL,
    kind TEXT NOT NULL,
    program_json TEXT NOT NULL,
    saved_at TEXT NOT NULL,
    PRIMARY KEY (language, year, week, kind)
);
CREATE TABLE IF NOT EXISTS downloads (
    ref_key TEXT PRIMARY KEY,
    ref_url TEXT NOT NULL,
    local_path TEXT NOT NULL,
    sha256 TEXT,
    downloaded_at TEXT NOT NULL
);
PRAGMA user_version = 1;
"""


class MeetingStorage:
    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(self.db_path)) as conn:
            conn.executescript(_SCHEMA)

    def save_program(self, prog: MeetingProgram) -> None:
        year, week, _ = prog.week_start.isocalendar()
        payload = prog.model_dump_json()
        with closing(sqlite3.connect(self.db_path)) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO programs "
                "(language, year, week, kind, program_json, saved_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
                    prog.language,
                    year,
                    week,
                    prog.kind.value,
                    payload,
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
            conn.commit()

    def load_program(
        self,
        *,
        language: str,
        year: int,
        week: int,
        kind: MeetingKind,
    ) -> MeetingProgram | None:
        with closing(sqlite3.connect(self.db_path)) as conn:
            row = conn.execute(
                "SELECT program_json FROM programs WHERE language=? AND year=? AND week=? AND kind=?",
                (language, year, week, kind.value),
            ).fetchone()
        if row is None:
            return None
        return MeetingProgram.model_validate_json(row[0])

    def mark_downloaded(self, ref: MediaRef, *, local_path: Path) -> None:
        key = ref.sha256 or ref.url
        with closing(sqlite3.connect(self.db_path)) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO downloads "
                "(ref_key, ref_url, local_path, sha256, downloaded_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (
                    key,
                    ref.url,
                    str(local_path),
                    ref.sha256,
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
            conn.commit()

    def is_downloaded(self, ref: MediaRef) -> bool:
        return self.get_download_info(ref) is not None

    def get_download_info(self, ref: MediaRef) -> dict | None:
        key = ref.sha256 or ref.url
        with closing(sqlite3.connect(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT ref_url, local_path, sha256, downloaded_at FROM downloads WHERE ref_key=?",
                (key,),
            ).fetchone()
        return dict(row) if row else None
