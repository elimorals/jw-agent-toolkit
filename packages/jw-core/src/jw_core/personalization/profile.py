"""User profile — preferences that shape every agent invocation.

Fields are conservative:
  - language (ISO)
  - congregation (free text — never sent off-device)
  - assignments  (typical roles: 'pioneer', 'elder', 'mst', 'aux_pioneer',
                  'household_head', 'sister', 'youth')
  - interests    (doctrinal topics that should pre-load in research)
  - tone         ('formal' | 'casual' | 'easy_read')
  - tts_provider (override)
  - rag_root     (override path for RAG store)

Stored in SQLite at `~/.jw-agent-toolkit/profile.db` (override
`JW_PROFILE_DB`). One row per `user_id` so multi-user setups can coexist.
"""

from __future__ import annotations

import json
import os
import sqlite3
import time
from dataclasses import dataclass, field
from pathlib import Path


def _default_db_path() -> Path:
    return Path(os.getenv("JW_PROFILE_DB", "~/.jw-agent-toolkit/profile.db")).expanduser()


@dataclass
class UserProfile:
    user_id: str = "default"
    language: str = "en"
    congregation: str = ""
    assignments: list[str] = field(default_factory=list)
    interests: list[str] = field(default_factory=list)
    tone: str = "formal"
    tts_provider: str = ""
    rag_root: str = ""
    updated_at_unix: float = 0.0

    @property
    def is_minor(self) -> bool:
        return "youth" in self.assignments


class UserProfileStore:
    SCHEMA = """
    CREATE TABLE IF NOT EXISTS profiles (
        user_id TEXT PRIMARY KEY,
        language TEXT NOT NULL DEFAULT 'en',
        congregation TEXT NOT NULL DEFAULT '',
        assignments TEXT NOT NULL DEFAULT '[]',
        interests TEXT NOT NULL DEFAULT '[]',
        tone TEXT NOT NULL DEFAULT 'formal',
        tts_provider TEXT NOT NULL DEFAULT '',
        rag_root TEXT NOT NULL DEFAULT '',
        updated_at_unix REAL NOT NULL
    );
    """

    def __init__(self, db_path: Path | str | None = None) -> None:
        self.path = Path(db_path).expanduser() if db_path else _default_db_path()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.path)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(self.SCHEMA)
        self._conn.commit()

    def upsert(self, profile: UserProfile) -> UserProfile:
        profile.updated_at_unix = time.time()
        self._conn.execute(
            "INSERT OR REPLACE INTO profiles "
            "(user_id, language, congregation, assignments, interests, tone, "
            "tts_provider, rag_root, updated_at_unix) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                profile.user_id,
                profile.language,
                profile.congregation,
                json.dumps(profile.assignments),
                json.dumps(profile.interests),
                profile.tone,
                profile.tts_provider,
                profile.rag_root,
                profile.updated_at_unix,
            ),
        )
        self._conn.commit()
        return profile

    def get(self, user_id: str = "default") -> UserProfile:
        row = self._conn.execute("SELECT * FROM profiles WHERE user_id = ?", (user_id,)).fetchone()
        if row is None:
            return UserProfile(user_id=user_id)
        return UserProfile(
            user_id=row["user_id"],
            language=row["language"],
            congregation=row["congregation"],
            assignments=json.loads(row["assignments"]),
            interests=json.loads(row["interests"]),
            tone=row["tone"],
            tts_provider=row["tts_provider"],
            rag_root=row["rag_root"],
            updated_at_unix=row["updated_at_unix"],
        )

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> UserProfileStore:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()


def default_profile(*, user_id: str = "default") -> UserProfile:
    return UserProfile(user_id=user_id, language="en", tone="formal")
