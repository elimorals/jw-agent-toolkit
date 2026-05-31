"""Spaced-repetition flashcards over Bible verses (SM-2 algorithm).

VISION.md item: "Flashcards / spaced repetition de pasajes clave".

SM-2 (SuperMemo-2) is the venerable algorithm used by Anki. We implement
a compact version:

  - Quality 0..5 (0 = forgot, 5 = perfect recall).
  - Easiness Factor (EF) starts at 2.5 and adjusts on each review.
  - First two correct reviews: 1 day → 6 days.
  - Then `interval *= EF`.

Cards live at `~/.jw-agent-toolkit/cards.db` (override `JW_CARDS_DB`).
"""

from __future__ import annotations

import os
import sqlite3
import time
import uuid
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path


def _default_db_path() -> Path:
    return Path(os.getenv("JW_CARDS_DB", "~/.jw-agent-toolkit/cards.db")).expanduser()


@dataclass
class Flashcard:
    card_id: str = ""
    front: str = ""  # Usually the reference, e.g. "John 3:16"
    back: str = ""  # Verse text or definition
    tags: list[str] = field(default_factory=list)
    ef: float = 2.5
    interval_days: int = 0
    repetitions: int = 0
    due_iso: str = ""
    created_at_unix: float = 0.0
    last_reviewed_unix: float = 0.0

    def ensure_id(self) -> None:
        if not self.card_id:
            self.card_id = uuid.uuid4().hex


def schedule_next_review(card: Flashcard, quality: int) -> Flashcard:
    """Apply SM-2 to compute next interval.

    Quality scale:
      5 - perfect response
      4 - correct after hesitation
      3 - correct with serious difficulty
      2 - incorrect, easy to recall once shown
      1 - incorrect, difficult to recall
      0 - total blackout
    """
    if quality < 0 or quality > 5:
        raise ValueError("quality must be 0..5")

    if quality < 3:
        card.repetitions = 0
        card.interval_days = 1
    else:
        if card.repetitions == 0:
            card.interval_days = 1
        elif card.repetitions == 1:
            card.interval_days = 6
        else:
            card.interval_days = max(1, round(card.interval_days * card.ef))
        card.repetitions += 1

    # Update EF (bounded at 1.3)
    card.ef = max(1.3, card.ef + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02)))
    card.due_iso = (date.today() + timedelta(days=card.interval_days)).isoformat()
    card.last_reviewed_unix = time.time()
    return card


def review_card(deck: FlashcardDeck, card_id: str, quality: int) -> Flashcard | None:
    """Convenience: read, update, persist."""
    card = deck.get(card_id)
    if card is None:
        return None
    schedule_next_review(card, quality)
    deck.upsert(card)
    return card


class FlashcardDeck:
    SCHEMA = """
    CREATE TABLE IF NOT EXISTS cards (
        card_id TEXT PRIMARY KEY,
        front TEXT NOT NULL,
        back TEXT NOT NULL,
        tags TEXT NOT NULL DEFAULT '',
        ef REAL NOT NULL DEFAULT 2.5,
        interval_days INTEGER NOT NULL DEFAULT 0,
        repetitions INTEGER NOT NULL DEFAULT 0,
        due_iso TEXT NOT NULL DEFAULT '',
        created_at_unix REAL NOT NULL,
        last_reviewed_unix REAL NOT NULL DEFAULT 0
    );
    CREATE INDEX IF NOT EXISTS idx_due ON cards (due_iso);
    """

    def __init__(self, db_path: Path | str | None = None) -> None:
        self.path = Path(db_path).expanduser() if db_path else _default_db_path()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.path)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(self.SCHEMA)
        self._conn.commit()

    def upsert(self, card: Flashcard) -> Flashcard:
        card.ensure_id()
        if not card.created_at_unix:
            card.created_at_unix = time.time()
        self._conn.execute(
            "INSERT OR REPLACE INTO cards "
            "(card_id, front, back, tags, ef, interval_days, repetitions, due_iso, "
            "created_at_unix, last_reviewed_unix) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                card.card_id,
                card.front,
                card.back,
                ",".join(card.tags),
                card.ef,
                card.interval_days,
                card.repetitions,
                card.due_iso,
                card.created_at_unix,
                card.last_reviewed_unix,
            ),
        )
        self._conn.commit()
        return card

    def get(self, card_id: str) -> Flashcard | None:
        cur = self._conn.execute("SELECT * FROM cards WHERE card_id = ?", (card_id,))
        row = cur.fetchone()
        return _row_to_card(row) if row else None

    def due_today(self) -> list[Flashcard]:
        today = date.today().isoformat()
        cur = self._conn.execute(
            "SELECT * FROM cards WHERE due_iso <= ? OR due_iso = '' ORDER BY due_iso",
            (today,),
        )
        return [_row_to_card(r) for r in cur.fetchall()]

    def all(self) -> list[Flashcard]:
        cur = self._conn.execute("SELECT * FROM cards ORDER BY created_at_unix DESC")
        return [_row_to_card(r) for r in cur.fetchall()]

    def delete(self, card_id: str) -> bool:
        cur = self._conn.execute("DELETE FROM cards WHERE card_id = ?", (card_id,))
        self._conn.commit()
        return cur.rowcount > 0

    def stats(self) -> dict[str, int]:
        total = self._conn.execute("SELECT COUNT(*) FROM cards").fetchone()[0]
        today = date.today().isoformat()
        due = self._conn.execute(
            "SELECT COUNT(*) FROM cards WHERE due_iso <= ? OR due_iso = ''",
            (today,),
        ).fetchone()[0]
        return {"total": total, "due_today": due}

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> FlashcardDeck:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()


def _row_to_card(row: sqlite3.Row) -> Flashcard:
    return Flashcard(
        card_id=row["card_id"],
        front=row["front"],
        back=row["back"],
        tags=row["tags"].split(",") if row["tags"] else [],
        ef=row["ef"],
        interval_days=row["interval_days"],
        repetitions=row["repetitions"],
        due_iso=row["due_iso"],
        created_at_unix=row["created_at_unix"],
        last_reviewed_unix=row["last_reviewed_unix"],
    )
