"""SparSession cross-process persistence via SQLite (Fase 66 post-MVP).

Sessions live in `~/.jw-agent-toolkit/spar/sessions.sqlite` (or
`JW_SPAR_SESSIONS_DB` override). Each session is stored as a single row
with `model_dump_json()` of the `SparSession`. Save on every mutation
keeps the on-disk copy authoritative and consistent across processes.
"""

from __future__ import annotations

import logging
import os
import sqlite3
from pathlib import Path

from jw_agents.spar.models import SparSession

logger = logging.getLogger(__name__)


def default_db_path() -> Path:
    override = os.environ.get("JW_SPAR_SESSIONS_DB")
    if override:
        return Path(override).expanduser()
    return Path(
        "~/.jw-agent-toolkit/spar/sessions.sqlite"
    ).expanduser()


def _open(db_path: Path | None = None) -> sqlite3.Connection:
    p = db_path or default_db_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(p)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS sessions (
            session_id TEXT PRIMARY KEY,
            payload TEXT NOT NULL,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.commit()
    return conn


def save_session(
    session: SparSession, *, db_path: Path | None = None
) -> None:
    """Insert-or-replace the session row."""
    conn = _open(db_path)
    try:
        conn.execute(
            "INSERT OR REPLACE INTO sessions (session_id, payload, updated_at) "
            "VALUES (?, ?, CURRENT_TIMESTAMP)",
            (session.session_id, session.model_dump_json()),
        )
        conn.commit()
    finally:
        conn.close()


def load_session(
    session_id: str, *, db_path: Path | None = None
) -> SparSession | None:
    """Return the persisted session, or None if absent."""
    conn = _open(db_path)
    try:
        cur = conn.execute(
            "SELECT payload FROM sessions WHERE session_id = ?",
            (session_id,),
        )
        row = cur.fetchone()
    finally:
        conn.close()
    if row is None:
        return None
    return SparSession.model_validate_json(row[0])


def list_persisted(*, db_path: Path | None = None) -> list[str]:
    """All persisted session ids in insertion order."""
    conn = _open(db_path)
    try:
        cur = conn.execute(
            "SELECT session_id FROM sessions ORDER BY updated_at DESC"
        )
        return [r[0] for r in cur]
    finally:
        conn.close()


def delete_persisted(
    session_id: str, *, db_path: Path | None = None
) -> bool:
    """Delete by id. Returns True if a row was removed."""
    conn = _open(db_path)
    try:
        cur = conn.execute(
            "DELETE FROM sessions WHERE session_id = ?", (session_id,)
        )
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def reload_into_registry(
    session_id: str, *, db_path: Path | None = None
) -> SparSession:
    """Load `session_id` from disk and place it in the in-process registry.

    This is what enables cross-process resume: process A starts a
    session and exits; process B calls `reload_into_registry("sid")` and
    then continues with `take_turn(session_id, ...)`.

    Raises `KeyError` if not on disk.
    """
    from jw_agents.spar import session as _session_module

    persisted = load_session(session_id, db_path=db_path)
    if persisted is None:
        raise KeyError(session_id)
    _session_module._SESSIONS[session_id] = persisted
    return persisted
