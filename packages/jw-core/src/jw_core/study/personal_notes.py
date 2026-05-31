"""Per-verse personal notes — SQLite store + RAG export.

VISION.md item: "Notas personales asociadas a versículos, persistentes y
buscables vía RAG".

Notes live at `~/.jw-agent-toolkit/notes.db` (override `JW_NOTES_DB`).
FTS5-indexed so local search works without the RAG store; the
`notes_to_rag_chunks` helper converts notes into chunk dicts ready to
add to a `jw_rag.VectorStore`.
"""

from __future__ import annotations

import os
import sqlite3
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from jw_core.privacy.encryption import FieldEncryptor


def _default_db_path() -> Path:
    return Path(os.getenv("JW_NOTES_DB", "~/.jw-agent-toolkit/notes.db")).expanduser()


@dataclass
class PersonalNote:
    book_num: int
    chapter: int
    verse: int | None = None
    note_id: str = ""
    title: str = ""
    body: str = ""
    tags: list[str] = field(default_factory=list)
    language: str = "en"
    created_at_unix: float = 0.0
    updated_at_unix: float = 0.0

    def ensure_id(self) -> None:
        if not self.note_id:
            self.note_id = uuid.uuid4().hex

    def anchor(self) -> str:
        if self.verse is None:
            return f"{self.book_num}:{self.chapter}"
        return f"{self.book_num}:{self.chapter}:{self.verse}"


class PersonalNoteStore:
    SCHEMA = """
    CREATE TABLE IF NOT EXISTS notes (
        note_id TEXT PRIMARY KEY,
        book_num INTEGER NOT NULL,
        chapter INTEGER NOT NULL,
        verse INTEGER,
        title TEXT NOT NULL DEFAULT '',
        body TEXT NOT NULL,
        tags TEXT NOT NULL DEFAULT '',
        language TEXT NOT NULL DEFAULT 'en',
        created_at_unix REAL NOT NULL,
        updated_at_unix REAL NOT NULL
    );
    CREATE INDEX IF NOT EXISTS idx_anchor ON notes (book_num, chapter, verse);
    CREATE VIRTUAL TABLE IF NOT EXISTS notes_fts USING fts5(note_id UNINDEXED, title, body);
    CREATE TRIGGER IF NOT EXISTS notes_ai AFTER INSERT ON notes BEGIN
        INSERT INTO notes_fts (note_id, title, body) VALUES (new.note_id, new.title, new.body);
    END;
    CREATE TRIGGER IF NOT EXISTS notes_ad AFTER DELETE ON notes BEGIN
        DELETE FROM notes_fts WHERE note_id = old.note_id;
    END;
    CREATE TRIGGER IF NOT EXISTS notes_au AFTER UPDATE ON notes BEGIN
        DELETE FROM notes_fts WHERE note_id = old.note_id;
        INSERT INTO notes_fts (note_id, title, body) VALUES (new.note_id, new.title, new.body);
    END;
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
        # When JW_PRIVACY_KEY is set, encryptor.enabled is True and body/title
        # are stored as Fernet ciphertext. Otherwise it's a transparent passthrough.
        self._enc = encryptor if encryptor is not None else FieldEncryptor()

    def add(self, note: PersonalNote) -> PersonalNote:
        note.ensure_id()
        now = time.time()
        if not note.created_at_unix:
            note.created_at_unix = now
        note.updated_at_unix = now
        self._conn.execute(
            "INSERT OR REPLACE INTO notes "
            "(note_id, book_num, chapter, verse, title, body, tags, language, "
            "created_at_unix, updated_at_unix) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                note.note_id,
                note.book_num,
                note.chapter,
                note.verse,
                self._enc.encrypt(note.title),
                self._enc.encrypt(note.body),
                ",".join(note.tags),
                note.language,
                note.created_at_unix,
                note.updated_at_unix,
            ),
        )
        self._conn.commit()
        return note

    def get(self, note_id: str) -> PersonalNote | None:
        cur = self._conn.execute("SELECT * FROM notes WHERE note_id = ?", (note_id,))
        row = cur.fetchone()
        return self._row_to_note(row) if row else None

    def for_anchor(self, book_num: int, chapter: int, verse: int | None = None) -> list[PersonalNote]:
        if verse is None:
            cur = self._conn.execute(
                "SELECT * FROM notes WHERE book_num = ? AND chapter = ? ORDER BY verse",
                (book_num, chapter),
            )
        else:
            cur = self._conn.execute(
                "SELECT * FROM notes WHERE book_num = ? AND chapter = ? AND verse = ? ORDER BY created_at_unix",
                (book_num, chapter, verse),
            )
        return [self._row_to_note(r) for r in cur.fetchall()]

    def search(self, query: str, *, top_k: int = 20) -> list[PersonalNote]:
        # FTS5 phrase search. When encryption is enabled, the FTS index
        # contains ciphertext — local fallback scans cleartext rows.
        if self._enc.enabled:
            return [n for n in self.list_all() if query.lower() in n.body.lower()][:top_k]
        cur = self._conn.execute(
            "SELECT n.* FROM notes n JOIN notes_fts f ON n.note_id = f.note_id "
            "WHERE notes_fts MATCH ? ORDER BY rank LIMIT ?",
            (query, top_k),
        )
        return [self._row_to_note(r) for r in cur.fetchall()]

    def list_all(self, *, tag: str | None = None) -> list[PersonalNote]:
        if tag:
            cur = self._conn.execute(
                "SELECT * FROM notes WHERE tags LIKE ? ORDER BY updated_at_unix DESC",
                (f"%{tag}%",),
            )
        else:
            cur = self._conn.execute("SELECT * FROM notes ORDER BY updated_at_unix DESC")
        return [self._row_to_note(r) for r in cur.fetchall()]

    def delete(self, note_id: str) -> bool:
        cur = self._conn.execute("DELETE FROM notes WHERE note_id = ?", (note_id,))
        self._conn.commit()
        return cur.rowcount > 0

    def stats(self) -> dict[str, int]:
        return {
            "total": self._conn.execute("SELECT COUNT(*) FROM notes").fetchone()[0],
        }

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> PersonalNoteStore:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def _row_to_note(self, row: sqlite3.Row) -> PersonalNote:
        return PersonalNote(
            note_id=row["note_id"],
            book_num=row["book_num"],
            chapter=row["chapter"],
            verse=row["verse"],
            title=self._enc.decrypt(row["title"]) if row["title"] else "",
            body=self._enc.decrypt(row["body"]) if row["body"] else "",
            tags=row["tags"].split(",") if row["tags"] else [],
            language=row["language"],
            created_at_unix=row["created_at_unix"],
            updated_at_unix=row["updated_at_unix"],
        )


def _row_to_note(row: sqlite3.Row) -> PersonalNote:
    """Free-function fallback (no decryption — used by tests that don't set a key)."""
    return PersonalNote(
        note_id=row["note_id"],
        book_num=row["book_num"],
        chapter=row["chapter"],
        verse=row["verse"],
        title=row["title"],
        body=row["body"],
        tags=row["tags"].split(",") if row["tags"] else [],
        language=row["language"],
        created_at_unix=row["created_at_unix"],
        updated_at_unix=row["updated_at_unix"],
    )


def notes_to_rag_chunks(notes: list[PersonalNote]) -> list[dict[str, Any]]:
    """Render a list of notes as RAG-ready chunks (no embedding done).

    Caller can feed each dict into `jw_rag.Chunk(**d)` semantics.
    """
    chunks = []
    for n in notes:
        chunks.append(
            {
                "id": f"note:{n.note_id}",
                "text": f"{n.title}\n\n{n.body}".strip(),
                "metadata": {
                    "kind": "personal_note",
                    "anchor": n.anchor(),
                    "book_num": n.book_num,
                    "chapter": n.chapter,
                    "verse": n.verse,
                    "language": n.language,
                    "tags": n.tags,
                },
            }
        )
    return chunks
