"""revisit_tracker — privacy-first tracker for return visits.

Storage: a SQLite DB at `~/.jw-agent-toolkit/ministry.db` (override via
`JW_MINISTRY_DB`). Optional field-level Fernet encryption when the user
provides `JW_MINISTRY_KEY` (a urlsafe base64 32-byte key) — when absent
fields are stored in cleartext but ON DEVICE only.

This explicitly does NOT sync anywhere. Per VISION.md: "Tracker de
hermanos / personas sin opt-in" is on the do-not-do list; this tracker
exists for the local Witness's own ministry notes and never leaves the
device.
"""

from __future__ import annotations

import json
import os
import sqlite3
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from jw_core.privacy.encryption import FieldEncryptor


def _default_db_path() -> Path:
    raw = os.getenv("JW_MINISTRY_DB", "~/.jw-agent-toolkit/ministry.db")
    return Path(raw).expanduser()


@dataclass
class Revisit:
    interest_id: str
    name_alias: str = "(anonymous)"
    location_hint: str = ""
    language: str = "en"
    last_topic: str = ""
    notes: str = ""
    next_visit_iso: str = ""
    created_at_unix: float = 0.0
    updated_at_unix: float = 0.0
    tags: list[str] = field(default_factory=list)

    def to_row(self) -> dict[str, Any]:
        return {
            "interest_id": self.interest_id,
            "name_alias": self.name_alias,
            "location_hint": self.location_hint,
            "language": self.language,
            "last_topic": self.last_topic,
            "notes": self.notes,
            "next_visit_iso": self.next_visit_iso,
            "created_at_unix": self.created_at_unix,
            "updated_at_unix": self.updated_at_unix,
            "tags": json.dumps(self.tags),
        }

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> Revisit:
        return cls(
            interest_id=row["interest_id"],
            name_alias=row["name_alias"],
            location_hint=row["location_hint"],
            language=row["language"],
            last_topic=row["last_topic"],
            notes=row["notes"],
            next_visit_iso=row["next_visit_iso"],
            created_at_unix=row["created_at_unix"],
            updated_at_unix=row["updated_at_unix"],
            tags=json.loads(row["tags"]) if row["tags"] else [],
        )


class RevisitStore:
    """Tiny SQLite-backed store for revisit notes."""

    SCHEMA = """
    CREATE TABLE IF NOT EXISTS revisits (
        interest_id TEXT PRIMARY KEY,
        name_alias TEXT NOT NULL,
        location_hint TEXT NOT NULL DEFAULT '',
        language TEXT NOT NULL DEFAULT 'en',
        last_topic TEXT NOT NULL DEFAULT '',
        notes TEXT NOT NULL DEFAULT '',
        next_visit_iso TEXT NOT NULL DEFAULT '',
        created_at_unix REAL NOT NULL,
        updated_at_unix REAL NOT NULL,
        tags TEXT NOT NULL DEFAULT '[]'
    );
    CREATE INDEX IF NOT EXISTS idx_next_visit ON revisits (next_visit_iso);
    CREATE INDEX IF NOT EXISTS idx_language ON revisits (language);
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
        self._conn.executescript(self.SCHEMA)
        self._conn.commit()
        self._enc = encryptor if encryptor is not None else FieldEncryptor()

    def _encrypt(self, rev: Revisit) -> Revisit:
        if not self._enc.enabled:
            return rev
        rev_copy = Revisit(**{**rev.__dict__})
        rev_copy.notes = self._enc.encrypt(rev.notes)
        rev_copy.name_alias = self._enc.encrypt(rev.name_alias)
        rev_copy.location_hint = self._enc.encrypt(rev.location_hint)
        return rev_copy

    def _decrypt_row(self, row: sqlite3.Row) -> Revisit:
        rev = Revisit.from_row(row)
        if self._enc.enabled:
            rev.notes = self._enc.decrypt(rev.notes) if rev.notes else ""
            rev.name_alias = self._enc.decrypt(rev.name_alias) if rev.name_alias else ""
            rev.location_hint = self._enc.decrypt(rev.location_hint) if rev.location_hint else ""
        return rev

    def upsert(self, revisit: Revisit) -> Revisit:
        now = time.time()
        if not revisit.created_at_unix:
            revisit.created_at_unix = now
        revisit.updated_at_unix = now
        to_store = self._encrypt(revisit)
        row = to_store.to_row()
        cols = ", ".join(row.keys())
        placeholders = ", ".join(f":{k}" for k in row.keys())
        updates = ", ".join(f"{k}=excluded.{k}" for k in row.keys() if k != "interest_id")
        sql = f"INSERT INTO revisits ({cols}) VALUES ({placeholders}) ON CONFLICT(interest_id) DO UPDATE SET {updates}"
        self._conn.execute(sql, row)
        self._conn.commit()
        return revisit

    def get(self, interest_id: str) -> Revisit | None:
        cur = self._conn.execute("SELECT * FROM revisits WHERE interest_id = ?", (interest_id,))
        row = cur.fetchone()
        return self._decrypt_row(row) if row else None

    def list_all(self, *, language: str | None = None) -> list[Revisit]:
        if language:
            cur = self._conn.execute(
                "SELECT * FROM revisits WHERE language = ? ORDER BY next_visit_iso, name_alias",
                (language,),
            )
        else:
            cur = self._conn.execute("SELECT * FROM revisits ORDER BY next_visit_iso, name_alias")
        return [self._decrypt_row(r) for r in cur.fetchall()]

    def due(self, *, on_or_before: str) -> list[Revisit]:
        """Return revisits whose next_visit_iso is non-empty and <= cutoff."""
        cur = self._conn.execute(
            "SELECT * FROM revisits WHERE next_visit_iso != '' AND next_visit_iso <= ? ORDER BY next_visit_iso",
            (on_or_before,),
        )
        return [self._decrypt_row(r) for r in cur.fetchall()]

    def delete(self, interest_id: str) -> bool:
        cur = self._conn.execute("DELETE FROM revisits WHERE interest_id = ?", (interest_id,))
        self._conn.commit()
        return cur.rowcount > 0

    def search(self, query: str) -> list[Revisit]:
        if self._enc.enabled:
            # SQL LIKE doesn't see plaintext; decrypt all and filter in memory.
            q = query.lower()
            return [
                r
                for r in self.list_all()
                if q in r.notes.lower() or q in r.name_alias.lower() or q in r.last_topic.lower()
            ]
        q = f"%{query.lower()}%"
        cur = self._conn.execute(
            "SELECT * FROM revisits WHERE LOWER(notes) LIKE ? OR LOWER(name_alias) LIKE ? OR LOWER(last_topic) LIKE ?",
            (q, q, q),
        )
        return [self._decrypt_row(r) for r in cur.fetchall()]

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> RevisitStore:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()


def plan_next_visit(revisit: Revisit, *, language: str = "en") -> dict[str, Any]:
    """Generate a plan-for-next-visit checklist based on `last_topic`."""
    intros = {
        "en": "When you return, gently bring back the conversation by referring to:",
        "es": "Cuando regrese, retome la conversación haciendo referencia a:",
        "pt": "Quando voltar, retome a conversa fazendo referência a:",
    }
    return {
        "interest_id": revisit.interest_id,
        "intro": intros.get(language, intros["en"]),
        "anchor_topic": revisit.last_topic or "(no topic recorded yet)",
        "warm_up_question": _warmup_question(revisit.last_topic, language),
        "next_visit_iso": revisit.next_visit_iso,
        "language": revisit.language,
    }


def _warmup_question(topic: str, language: str) -> str:
    if not topic:
        return ""
    templates = {
        "en": f"Would you mind if I continued where we left off — we were talking about {topic}?",
        "es": f"¿Le parece bien si retomamos lo que estuvimos viendo sobre {topic}?",
        "pt": f"O senhor se importa se continuarmos de onde paramos — falávamos sobre {topic}?",
    }
    return templates.get(language, templates["en"])
