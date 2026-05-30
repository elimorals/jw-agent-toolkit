"""Cross-session memory ("ayer estábamos viendo X, continuamos...").

Each memory entry has:
  - `kind` ('topic', 'verse_ref', 'open_question', 'last_revisit', 'free_note')
  - `text` (the actual content)
  - `metadata` (free dict)
  - `timestamp`

Stored in a SQLite append-log; the most recent N entries per user are
considered the active "memory horizon".

Use `load_memory_for_user(user_id, kinds=...)` to fetch and inject into a
prompt; use `save_memory_for_user(user_id, MemoryEntry(...))` after each
substantive interaction.
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
    return Path(os.getenv("JW_MEMORY_DB", "~/.jw-agent-toolkit/memory.db")).expanduser()


@dataclass
class MemoryEntry:
    kind: str
    text: str
    user_id: str = "default"
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at_unix: float = 0.0
    entry_id: int = 0


class SessionMemory:
    SCHEMA = """
    CREATE TABLE IF NOT EXISTS memory (
        entry_id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT NOT NULL,
        kind TEXT NOT NULL,
        text TEXT NOT NULL,
        metadata TEXT NOT NULL DEFAULT '{}',
        created_at_unix REAL NOT NULL
    );
    CREATE INDEX IF NOT EXISTS idx_user_kind ON memory (user_id, kind);
    """

    def __init__(
        self,
        db_path: Path | str | None = None,
        *,
        encryptor: FieldEncryptor | None = None,
    ) -> None:
        self.path = Path(db_path).expanduser() if db_path else _default_db_path()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.path)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(self.SCHEMA)
        self._conn.commit()
        self._enc = encryptor if encryptor is not None else FieldEncryptor()

    def add(self, entry: MemoryEntry) -> MemoryEntry:
        if not entry.created_at_unix:
            entry.created_at_unix = time.time()
        cur = self._conn.execute(
            "INSERT INTO memory (user_id, kind, text, metadata, created_at_unix) "
            "VALUES (?, ?, ?, ?, ?)",
            (
                entry.user_id,
                entry.kind,
                self._enc.encrypt(entry.text),
                self._enc.encrypt(json.dumps(entry.metadata)),
                entry.created_at_unix,
            ),
        )
        entry.entry_id = cur.lastrowid or 0
        self._conn.commit()
        return entry

    def recent(
        self,
        user_id: str = "default",
        *,
        limit: int = 20,
        kinds: list[str] | None = None,
    ) -> list[MemoryEntry]:
        sql = "SELECT * FROM memory WHERE user_id = ? "
        params: list[object] = [user_id]
        if kinds:
            placeholders = ",".join("?" for _ in kinds)
            sql += f"AND kind IN ({placeholders}) "
            params.extend(kinds)
        sql += "ORDER BY created_at_unix DESC LIMIT ?"
        params.append(limit)
        rows = self._conn.execute(sql, params).fetchall()
        return [
            MemoryEntry(
                entry_id=r["entry_id"],
                user_id=r["user_id"],
                kind=r["kind"],
                text=self._enc.decrypt(r["text"]) if r["text"] else "",
                metadata=json.loads(self._enc.decrypt(r["metadata"]) if r["metadata"] else "{}"),
                created_at_unix=r["created_at_unix"],
            )
            for r in rows
        ]

    def clear(self, user_id: str = "default") -> int:
        cur = self._conn.execute("DELETE FROM memory WHERE user_id = ?", (user_id,))
        self._conn.commit()
        return cur.rowcount

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> SessionMemory:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()


def save_memory_for_user(user_id: str, entry: MemoryEntry) -> MemoryEntry:
    with SessionMemory() as mem:
        entry.user_id = user_id
        return mem.add(entry)


def load_memory_for_user(
    user_id: str = "default",
    *,
    limit: int = 20,
    kinds: list[str] | None = None,
) -> list[MemoryEntry]:
    with SessionMemory() as mem:
        return mem.recent(user_id, limit=limit, kinds=kinds)
