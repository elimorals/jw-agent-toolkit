"""StudentProgress — local-only encryptable store for the study-book lifecycle.

VISION rule: "No tracker de hermanos sin opt-in". This IS a tracker, so:
  - First-run requires an explicit y/N consent + passphrase.
  - student_id is an alias (regex `^[a-z0-9_-]{3,32}$`), never a real name.
  - Free-text `notes` are Fernet-encrypted at rest with a key derived
    from the user's passphrase (PBKDF2-HMAC-SHA256, persistent salt).
  - Storage is ON DEVICE only. No sync. No telemetry.
"""

from __future__ import annotations

import json
import os
import secrets
import sqlite3
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path

from pydantic import BaseModel, Field

from jw_core.privacy.encryption import FieldEncryptor, derive_key_from_password


class LessonStatus(str, Enum):
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETED   = "completed"
    SKIPPED     = "skipped"


class GoalKind(str, Enum):
    ATTEND_MEETINGS         = "attend_meetings"
    DROP_ADDICTION_SMOKING  = "drop_addiction_smoking"
    DROP_ADDICTION_ALCOHOL  = "drop_addiction_alcohol"
    DROP_ADDICTION_OTHER    = "drop_addiction_other"
    PRAY_DAILY              = "pray_daily"
    FAMILY_WORSHIP          = "family_worship"
    BAPTISM                 = "baptism"
    OTHER                   = "other"


class StudentGoal(BaseModel):
    kind: GoalKind
    note: str = ""
    set_at_iso: str
    achieved_at_iso: str | None = None
    target_iso: str | None = None


class LessonRow(BaseModel):
    student_id: str = Field(pattern=r"^[a-z0-9_-]{3,32}$")
    book_pub: str
    lesson: int = Field(ge=1)
    status: LessonStatus = LessonStatus.NOT_STARTED
    notes: str = ""
    goals: list[StudentGoal] = []
    started_at_iso: str | None = None
    completed_at_iso: str | None = None
    attended_meetings_count: int = 0
    baptism_target_iso: str | None = None
    updated_at_iso: str


# --- Task 5: passphrase + salt persistence -------------------------------


class PrivacyState(str, Enum):
    CREATED = "created"
    LOADED  = "loaded"


def default_salt_path() -> Path:
    raw = os.getenv("JW_STUDY_SALT", "~/.jw-agent-toolkit/study_progress.salt")
    return Path(raw).expanduser()


def default_db_path() -> Path:
    raw = os.getenv("JW_STUDY_DB", "~/.jw-agent-toolkit/study_progress.db")
    return Path(raw).expanduser()


def load_or_create_salt(path: Path) -> PrivacyState:
    """Persistent 16-byte salt. Created with `secrets.token_bytes` on first call."""

    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        return PrivacyState.LOADED
    path.write_bytes(secrets.token_bytes(16))
    return PrivacyState.CREATED


def derive_encryptor_for_passphrase(
    passphrase: str, *, salt_path: Path | None = None
) -> FieldEncryptor:
    """Derive a FieldEncryptor from passphrase + persistent salt."""

    salt_path = salt_path or default_salt_path()
    load_or_create_salt(salt_path)
    salt = salt_path.read_bytes()
    key = derive_key_from_password(passphrase, salt=salt)
    return FieldEncryptor(key=key)


# --- Task 6: SQLite store with optional encrypted notes ------------------


class StudentProgressStore:
    SCHEMA = """
    CREATE TABLE IF NOT EXISTS lessons (
        student_id TEXT NOT NULL,
        book_pub TEXT NOT NULL,
        lesson INTEGER NOT NULL,
        status TEXT NOT NULL DEFAULT 'not_started',
        notes TEXT NOT NULL DEFAULT '',
        goals_json TEXT NOT NULL DEFAULT '[]',
        started_at_iso TEXT,
        completed_at_iso TEXT,
        attended_meetings_count INTEGER NOT NULL DEFAULT 0,
        baptism_target_iso TEXT,
        updated_at_iso TEXT NOT NULL,
        PRIMARY KEY (student_id, book_pub, lesson)
    );
    CREATE INDEX IF NOT EXISTS idx_student ON lessons (student_id);
    CREATE INDEX IF NOT EXISTS idx_book ON lessons (book_pub);
    """

    def __init__(
        self,
        db_path: Path | str | None = None,
        *,
        encryptor: FieldEncryptor | None = None,
    ) -> None:
        self.path = Path(db_path).expanduser() if db_path else default_db_path()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.path)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(self.SCHEMA)
        self._conn.commit()
        self._enc = encryptor if encryptor is not None else FieldEncryptor()

    def _encrypt_notes(self, value: str) -> str:
        if self._enc.enabled and value:
            return self._enc.encrypt(value)
        return value

    def _decrypt_notes(self, value: str) -> str:
        if self._enc.enabled and value:
            try:
                return self._enc.decrypt(value)
            except Exception:
                return value
        return value

    def upsert(self, row: LessonRow) -> LessonRow:
        if not row.updated_at_iso:
            row.updated_at_iso = datetime.now(timezone.utc).isoformat()
        encrypted_notes = self._encrypt_notes(row.notes)
        goals_json = json.dumps([g.model_dump() for g in row.goals])
        self._conn.execute(
            """
            INSERT INTO lessons (student_id, book_pub, lesson, status, notes, goals_json,
                                 started_at_iso, completed_at_iso, attended_meetings_count,
                                 baptism_target_iso, updated_at_iso)
            VALUES (:sid, :pub, :lesson, :status, :notes, :goals,
                    :started, :completed, :attended, :baptism, :updated)
            ON CONFLICT(student_id, book_pub, lesson) DO UPDATE SET
                status=excluded.status,
                notes=excluded.notes,
                goals_json=excluded.goals_json,
                started_at_iso=excluded.started_at_iso,
                completed_at_iso=excluded.completed_at_iso,
                attended_meetings_count=excluded.attended_meetings_count,
                baptism_target_iso=excluded.baptism_target_iso,
                updated_at_iso=excluded.updated_at_iso
            """,
            {
                "sid": row.student_id, "pub": row.book_pub, "lesson": row.lesson,
                "status": row.status.value, "notes": encrypted_notes, "goals": goals_json,
                "started": row.started_at_iso, "completed": row.completed_at_iso,
                "attended": row.attended_meetings_count,
                "baptism": row.baptism_target_iso,
                "updated": row.updated_at_iso,
            },
        )
        self._conn.commit()
        return row

    def get(self, student_id: str, book_pub: str, lesson: int) -> LessonRow | None:
        cur = self._conn.execute(
            "SELECT * FROM lessons WHERE student_id=? AND book_pub=? AND lesson=?",
            (student_id, book_pub, lesson),
        )
        row = cur.fetchone()
        return self._row_to_model(row) if row else None

    def list_for_student(
        self, student_id: str, book_pub: str | None = None
    ) -> list[LessonRow]:
        if book_pub:
            cur = self._conn.execute(
                "SELECT * FROM lessons WHERE student_id=? AND book_pub=? ORDER BY lesson",
                (student_id, book_pub),
            )
        else:
            cur = self._conn.execute(
                "SELECT * FROM lessons WHERE student_id=? ORDER BY book_pub, lesson",
                (student_id,),
            )
        return [self._row_to_model(r) for r in cur.fetchall()]

    def _row_to_model(self, row: sqlite3.Row) -> LessonRow:
        goals_raw = json.loads(row["goals_json"] or "[]")
        return LessonRow(
            student_id=row["student_id"],
            book_pub=row["book_pub"],
            lesson=row["lesson"],
            status=LessonStatus(row["status"]),
            notes=self._decrypt_notes(row["notes"]),
            goals=[StudentGoal(**g) for g in goals_raw],
            started_at_iso=row["started_at_iso"],
            completed_at_iso=row["completed_at_iso"],
            attended_meetings_count=row["attended_meetings_count"],
            baptism_target_iso=row["baptism_target_iso"],
            updated_at_iso=row["updated_at_iso"],
        )

    def close(self) -> None:
        self._conn.close()


# --- Task 7: crisis scanner + set_goal helper ----------------------------

from jw_core.data.study_prompts import scan_for_crisis


def scan_lesson_for_crisis(row: LessonRow, *, language: str) -> list[str]:
    return scan_for_crisis(row.notes, language=language)


def set_goal_for_student(
    store: "StudentProgressStore",
    student_id: str,
    book_pub: str,
    lesson: int,
    *,
    kind: GoalKind,
    target_iso: str | None = None,
    note: str = "",
) -> LessonRow:
    """Append (or upsert) a goal on a student's lesson row."""

    row = store.get(student_id, book_pub, lesson)
    if row is None:
        row = LessonRow(
            student_id=student_id, book_pub=book_pub, lesson=lesson,
            updated_at_iso=datetime.now(timezone.utc).isoformat(),
        )
    now = datetime.now(timezone.utc).isoformat()
    # Replace existing goal of same kind; otherwise append.
    goals = [g for g in row.goals if g.kind != kind]
    goals.append(StudentGoal(kind=kind, set_at_iso=now, target_iso=target_iso, note=note))
    row.goals = goals
    if kind == GoalKind.BAPTISM and target_iso:
        row.baptism_target_iso = target_iso
    row.updated_at_iso = now
    store.upsert(row)
    return row
