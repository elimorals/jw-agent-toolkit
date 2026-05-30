"""Bible reading plans with daily tracking.

Ships with three plans:

  - `whole_bible_year`: 66 books in 365 days, ~3 chapters/day on average
  - `nt_90`: New Testament in 90 days
  - `chronological`: events in roughly historical order (Walk Thru the Bible
    style — simplified)

Tracker stores progress in a SQLite table keyed by `plan_key + interest_id`
(e.g. user can have multiple parallel reading plans by setting a tag).
"""

from __future__ import annotations

import os
import sqlite3
import time
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path


@dataclass
class ReadingDay:
    day_index: int  # 1-based
    label: str
    chapters: list[tuple[int, int]]  # (book_num, chapter)


@dataclass
class ReadingPlan:
    key: str
    title: dict[str, str]
    description: dict[str, str]
    days: list[ReadingDay] = field(default_factory=list)


# ── Helpers to build plans ───────────────────────────────────────────────


# Chapter counts per book (NWT-canonical). Index 0 unused; 1..66 maps to books.
_CHAPTER_COUNTS = [
    0,
    50,
    40,
    27,
    36,
    34,
    24,
    21,
    4,
    31,
    24,
    22,
    25,
    29,
    36,
    10,
    13,
    10,
    42,
    150,
    31,
    12,
    8,
    66,
    52,
    5,
    48,
    12,
    14,
    3,
    9,
    1,
    4,
    7,
    3,
    3,
    3,
    2,
    14,
    4,
    28,
    16,
    24,
    21,
    28,
    16,
    16,
    13,
    6,
    6,
    4,
    4,
    5,
    3,
    6,
    4,
    3,
    1,
    13,
    5,
    5,
    3,
    5,
    1,
    1,
    1,
    22,
]


def _whole_bible_plan() -> list[ReadingDay]:
    """Distribute all ~1189 chapters across 365 days."""
    total = sum(_CHAPTER_COUNTS[1:67])  # 1189
    days = 365
    per_day = total / days
    # Linear walk
    plan: list[ReadingDay] = []
    cursor_book = 1
    cursor_chapter = 1
    accumulated = 0.0
    for day_index in range(1, days + 1):
        target = round(per_day * day_index)
        chapters: list[tuple[int, int]] = []
        while accumulated < target and cursor_book <= 66:
            chapters.append((cursor_book, cursor_chapter))
            accumulated += 1
            cursor_chapter += 1
            if cursor_chapter > _CHAPTER_COUNTS[cursor_book]:
                cursor_book += 1
                cursor_chapter = 1
        label = (
            f"Day {day_index}: book {chapters[0][0]} ch {chapters[0][1]}-{chapters[-1][1]}"
            if chapters
            else f"Day {day_index}"
        )
        plan.append(ReadingDay(day_index=day_index, label=label, chapters=chapters))
    return plan


def _nt_plan_90() -> list[ReadingDay]:
    nt_chapters: list[tuple[int, int]] = []
    for book_num in range(40, 67):  # Matthew through Revelation
        for ch in range(1, _CHAPTER_COUNTS[book_num] + 1):
            nt_chapters.append((book_num, ch))
    days = 90
    per_day = len(nt_chapters) / days
    plan: list[ReadingDay] = []
    for day_index in range(1, days + 1):
        start_idx = int(round((day_index - 1) * per_day))
        end_idx = int(round(day_index * per_day))
        chunk = nt_chapters[start_idx:end_idx]
        label = f"NT day {day_index} ({len(chunk)} chapters)"
        plan.append(ReadingDay(day_index=day_index, label=label, chapters=chunk))
    return plan


def _chronological_plan() -> list[ReadingDay]:
    """A simplified chronological pass — Gen → Exo → Job → Lev → Num → Deu
    → Jos → Jdg → Rut → 1Sa → 1Ch → 2Sa ... etc.

    For brevity we keep the canonical order with a few swaps. Real
    chronological plans are subjective; we ship a defensible default.
    """
    order = (
        [1, 2, 18]  # Genesis, Exodus, Job
        + list(range(3, 18))
        + list(range(19, 40))
        + list(range(40, 67))
    )
    chapters: list[tuple[int, int]] = []
    for book_num in order:
        for ch in range(1, _CHAPTER_COUNTS[book_num] + 1):
            chapters.append((book_num, ch))
    days = 365
    per_day = len(chapters) / days
    plan: list[ReadingDay] = []
    for day_index in range(1, days + 1):
        s = int(round((day_index - 1) * per_day))
        e = int(round(day_index * per_day))
        plan.append(
            ReadingDay(
                day_index=day_index,
                label=f"Chronological day {day_index}",
                chapters=chapters[s:e],
            )
        )
    return plan


READING_PLANS: dict[str, ReadingPlan] = {
    "whole_bible_year": ReadingPlan(
        key="whole_bible_year",
        title={"en": "Whole Bible in a year", "es": "Toda la Biblia en un año", "pt": "Toda a Bíblia em um ano"},
        description={
            "en": "All 66 books across 365 days.",
            "es": "Los 66 libros distribuidos en 365 días.",
            "pt": "Os 66 livros distribuídos em 365 dias.",
        },
        days=_whole_bible_plan(),
    ),
    "nt_90": ReadingPlan(
        key="nt_90",
        title={"en": "New Testament in 90 days", "es": "NT en 90 días", "pt": "NT em 90 dias"},
        description={"en": "Matthew → Revelation.", "es": "Mateo → Revelación.", "pt": "Mateus → Apocalipse."},
        days=_nt_plan_90(),
    ),
    "chronological": ReadingPlan(
        key="chronological",
        title={
            "en": "Chronological Bible",
            "es": "Lectura cronológica",
            "pt": "Leitura cronológica",
        },
        description={
            "en": "Books in approximate historical order.",
            "es": "Libros en orden histórico aproximado.",
            "pt": "Livros em ordem histórica aproximada.",
        },
        days=_chronological_plan(),
    ),
}


def list_reading_plans(language: str = "en") -> list[dict[str, object]]:
    return [
        {
            "key": p.key,
            "title": p.title.get(language, p.title["en"]),
            "description": p.description.get(language, p.description["en"]),
            "days": len(p.days),
        }
        for p in READING_PLANS.values()
    ]


# ── Tracker ──────────────────────────────────────────────────────────────


def _default_db_path() -> Path:
    return Path(os.getenv("JW_STUDY_DB", "~/.jw-agent-toolkit/study.db")).expanduser()


class ReadingPlanTracker:
    """SQLite tracker for one or more reading plans."""

    SCHEMA = """
    CREATE TABLE IF NOT EXISTS reading_progress (
        plan_key TEXT NOT NULL,
        day_index INTEGER NOT NULL,
        completed_at_unix REAL NOT NULL,
        note TEXT NOT NULL DEFAULT '',
        PRIMARY KEY (plan_key, day_index)
    );
    """

    def __init__(self, db_path: Path | str | None = None) -> None:
        self.path = Path(db_path).expanduser() if db_path else _default_db_path()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.path)
        self._conn.executescript(self.SCHEMA)
        self._conn.commit()

    def mark_done(self, plan_key: str, day_index: int, note: str = "") -> None:
        self._conn.execute(
            "INSERT OR REPLACE INTO reading_progress (plan_key, day_index, completed_at_unix, note) "
            "VALUES (?, ?, ?, ?)",
            (plan_key, day_index, time.time(), note),
        )
        self._conn.commit()

    def is_done(self, plan_key: str, day_index: int) -> bool:
        cur = self._conn.execute(
            "SELECT 1 FROM reading_progress WHERE plan_key = ? AND day_index = ?",
            (plan_key, day_index),
        )
        return cur.fetchone() is not None

    def completed_days(self, plan_key: str) -> list[int]:
        cur = self._conn.execute(
            "SELECT day_index FROM reading_progress WHERE plan_key = ? ORDER BY day_index",
            (plan_key,),
        )
        return [r[0] for r in cur.fetchall()]

    def status(self, plan_key: str) -> dict[str, object]:
        plan = READING_PLANS.get(plan_key)
        if plan is None:
            return {"error": f"Unknown plan {plan_key!r}"}
        done = self.completed_days(plan_key)
        return {
            "plan_key": plan_key,
            "total_days": len(plan.days),
            "completed": len(done),
            "percent": round(len(done) / max(1, len(plan.days)) * 100, 1),
            "next_day_index": (max(done) + 1) if done else 1,
        }

    def upcoming(self, plan_key: str, *, count: int = 7) -> list[dict[str, object]]:
        plan = READING_PLANS.get(plan_key)
        if plan is None:
            return []
        done = set(self.completed_days(plan_key))
        upcoming = []
        for day in plan.days:
            if day.day_index in done:
                continue
            upcoming.append({"day": day.day_index, "label": day.label, "chapters": day.chapters})
            if len(upcoming) >= count:
                break
        return upcoming

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> ReadingPlanTracker:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()


def today_day_index(plan_key: str, *, start_date: date | str | None = None) -> int:
    """Compute today's day index assuming a `start_date` (defaults to today minus 0)."""
    plan = READING_PLANS.get(plan_key)
    if plan is None:
        return 1
    if start_date is None:
        return 1
    if isinstance(start_date, str):
        start_date = date.fromisoformat(start_date)
    elapsed = (date.today() - start_date).days
    return max(1, min(len(plan.days), elapsed + 1))
