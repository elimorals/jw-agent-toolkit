"""SqliteMemoryStore: persistencia local con cifrado Fernet opt-in.

Patrón heredado de F25 RevisitStore.

Esquema:
    CREATE TABLE records(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id TEXT NOT NULL,
        timestamp TEXT NOT NULL,
        kind TEXT NOT NULL,
        content BLOB NOT NULL,           -- bytes; plaintext UTF-8 o ciphertext Fernet
        metadata TEXT NOT NULL,          -- JSON
        encrypted INTEGER NOT NULL       -- 0 plain, 1 fernet
    )

Cifrado:
- Si env `JW_MEMORY_KEY` presente al record(), content se cifra antes de INSERT.
- recall() detecta el flag `encrypted` por fila y descifra si aplica.
- Si JW_MEMORY_KEY falta y hay rows con encrypted=1, recall raises.
"""
from __future__ import annotations

import json
import os
import sqlite3
from contextlib import closing
from datetime import datetime
from pathlib import Path

from jw_agents.memory.protocol import MemoryKind, MemoryRecord

_SCHEMA = """
CREATE TABLE IF NOT EXISTS records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    kind TEXT NOT NULL,
    content BLOB NOT NULL,
    metadata TEXT NOT NULL,
    encrypted INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_records_session_id ON records(session_id);
CREATE INDEX IF NOT EXISTS idx_records_kind ON records(kind);
PRAGMA user_version = 1;
"""


def _default_db_path() -> Path:
    base = Path(os.environ.get("JW_MEMORY_DB", "~/.jw-agent-toolkit/memory.db"))
    return base.expanduser()


def _load_fernet():
    key = os.environ.get("JW_MEMORY_KEY")
    if not key:
        return None
    try:
        from cryptography.fernet import Fernet
    except ImportError as exc:
        raise RuntimeError("cryptography package required for JW_MEMORY_KEY") from exc
    return Fernet(key.encode() if isinstance(key, str) else key)


class SqliteMemoryStore:
    """Persistencia local sqlite con cifrado opt-in."""

    def __init__(self, db_path: Path | None = None):
        self.db_path = Path(db_path) if db_path else _default_db_path()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(self.db_path)) as conn:
            conn.executescript(_SCHEMA)

    def record(self, record: MemoryRecord) -> None:
        fernet = _load_fernet()
        content_bytes = record.content.encode("utf-8")
        encrypted = 0
        if fernet is not None:
            content_bytes = fernet.encrypt(content_bytes)
            encrypted = 1
        with closing(sqlite3.connect(self.db_path)) as conn:
            conn.execute(
                "INSERT INTO records (session_id, timestamp, kind, content, metadata, encrypted) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
                    record.session_id,
                    record.timestamp.isoformat(),
                    record.kind,
                    content_bytes,
                    json.dumps(record.metadata, ensure_ascii=False),
                    encrypted,
                ),
            )
            conn.commit()

    def recall(
        self,
        *,
        session_id: str | None = None,
        query: str | None = None,
        kind: MemoryKind | None = None,
        limit: int = 10,
    ) -> list[MemoryRecord]:
        clauses, params = [], []
        if session_id is not None:
            clauses.append("session_id = ?")
            params.append(session_id)
        if kind is not None:
            clauses.append("kind = ?")
            params.append(kind)
        where = (" WHERE " + " AND ".join(clauses)) if clauses else ""

        with closing(sqlite3.connect(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            sql = (
                f"SELECT session_id, timestamp, kind, content, metadata, encrypted "
                f"FROM records{where} ORDER BY timestamp DESC LIMIT ?"
            )
            rows = conn.execute(sql, [*params, limit * 4]).fetchall()

        fernet = _load_fernet()
        records: list[MemoryRecord] = []
        for row in rows:
            content_blob = row["content"]
            if row["encrypted"]:
                if fernet is None:
                    raise RuntimeError(
                        "Database is encrypted but JW_MEMORY_KEY env var is not set"
                    )
                content_text = fernet.decrypt(content_blob).decode("utf-8")
            else:
                content_text = (
                    content_blob.decode("utf-8")
                    if isinstance(content_blob, bytes)
                    else content_blob
                )
            records.append(
                MemoryRecord(
                    session_id=row["session_id"],
                    timestamp=datetime.fromisoformat(row["timestamp"]),
                    kind=row["kind"],  # type: ignore[arg-type]
                    content=content_text,
                    metadata=json.loads(row["metadata"]),
                )
            )

        if query is not None:
            q = query.lower()
            records = [r for r in records if q in r.content.lower()]
            records.sort(
                key=lambda r: r.content.lower().count(q),
                reverse=True,
            )
        return records[:limit]

    def list_sessions(self) -> list[str]:
        with closing(sqlite3.connect(self.db_path)) as conn:
            rows = conn.execute("SELECT DISTINCT session_id FROM records").fetchall()
        return [r[0] for r in rows]

    def forget(self, session_id: str) -> int:
        with closing(sqlite3.connect(self.db_path)) as conn:
            cur = conn.execute("DELETE FROM records WHERE session_id = ?", (session_id,))
            conn.commit()
            return cur.rowcount
