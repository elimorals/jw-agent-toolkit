"""Tests for the personal-study module (Module 4)."""

from __future__ import annotations

import tempfile
from datetime import date
from pathlib import Path

from jw_core.study.flashcards import Flashcard, FlashcardDeck, review_card, schedule_next_review
from jw_core.study.originals import (
    StrongEntry,
    get_strong_entry,
    list_known_strongs,
    register_strong_dump,
)
from jw_core.study.personal_notes import PersonalNote, PersonalNoteStore, notes_to_rag_chunks
from jw_core.study.reading_plan import (
    READING_PLANS,
    ReadingPlanTracker,
    list_reading_plans,
)


def _tmp_db() -> Path:
    return Path(tempfile.mkdtemp()) / "study.db"


# ── Reading plans ────────────────────────────────────────────────────────


def test_three_plans_registered() -> None:
    keys = set(READING_PLANS.keys())
    assert {"whole_bible_year", "nt_90", "chronological"} <= keys


def test_whole_bible_plan_covers_1189_chapters() -> None:
    plan = READING_PLANS["whole_bible_year"]
    total = sum(len(d.chapters) for d in plan.days)
    assert total == 1189
    assert len(plan.days) == 365


def test_nt90_covers_nt_only() -> None:
    plan = READING_PLANS["nt_90"]
    chapters = [c for d in plan.days for c in d.chapters]
    assert all(book >= 40 for book, _ in chapters)
    assert len(plan.days) == 90


def test_list_reading_plans_localizes() -> None:
    items_en = list_reading_plans("en")
    items_es = list_reading_plans("es")
    assert items_en[0]["title"] != items_es[0]["title"]


def test_tracker_marks_and_lists() -> None:
    path = _tmp_db()
    with ReadingPlanTracker(path) as tracker:
        tracker.mark_done("whole_bible_year", 1)
        tracker.mark_done("whole_bible_year", 2)
        assert tracker.is_done("whole_bible_year", 1)
        status = tracker.status("whole_bible_year")
        assert status["completed"] == 2
        upcoming = tracker.upcoming("whole_bible_year", count=3)
        assert {u["day"] for u in upcoming} == {3, 4, 5}


# ── Personal notes ───────────────────────────────────────────────────────


def test_note_store_add_and_search() -> None:
    path = _tmp_db()
    with PersonalNoteStore(path) as store:
        store.add(
            PersonalNote(
                book_num=43,
                chapter=3,
                verse=16,
                title="God's love",
                body="The most loved verse — covers Jesus' redemptive sacrifice.",
                tags=["love", "salvation"],
            )
        )
        store.add(
            PersonalNote(book_num=1, chapter=1, verse=1, title="Beginnings", body="In the beginning"),
        )
        hits = store.search("redemptive")
    assert any("redemptive" in n.body for n in hits)


def test_note_anchor_filter() -> None:
    path = _tmp_db()
    with PersonalNoteStore(path) as store:
        store.add(PersonalNote(book_num=1, chapter=1, verse=1, body="A"))
        store.add(PersonalNote(book_num=1, chapter=1, verse=2, body="B"))
        for_verse_one = store.for_anchor(1, 1, 1)
        for_chapter = store.for_anchor(1, 1)
    assert len(for_verse_one) == 1
    assert len(for_chapter) == 2


def test_notes_to_rag_chunks_shape() -> None:
    note = PersonalNote(book_num=43, chapter=3, verse=16, title="T", body="B", language="en")
    note.ensure_id()
    chunks = notes_to_rag_chunks([note])
    assert chunks[0]["metadata"]["anchor"] == "43:3:16"
    assert "T" in chunks[0]["text"]


# ── Flashcards (SM-2) ────────────────────────────────────────────────────


def test_sm2_quality_below_three_resets() -> None:
    card = Flashcard(repetitions=4, interval_days=30, ef=2.5)
    schedule_next_review(card, 2)
    assert card.repetitions == 0
    assert card.interval_days == 1


def test_sm2_first_correct_review_intervals() -> None:
    card = Flashcard()
    schedule_next_review(card, 5)
    assert card.interval_days == 1
    schedule_next_review(card, 5)
    assert card.interval_days == 6


def test_sm2_due_iso_set() -> None:
    card = Flashcard()
    schedule_next_review(card, 5)
    assert card.due_iso == (date.today().resolve() if False else date.fromisoformat(card.due_iso)).isoformat()


def test_deck_due_today_after_create() -> None:
    path = _tmp_db()
    with FlashcardDeck(path) as deck:
        deck.upsert(Flashcard(front="John 3:16", back="For God so loved..."))
        due = deck.due_today()
    assert len(due) == 1
    assert due[0].front == "John 3:16"


def test_review_card_persists_changes() -> None:
    path = _tmp_db()
    with FlashcardDeck(path) as deck:
        card = deck.upsert(Flashcard(front="X", back="Y"))
        reviewed = review_card(deck, card.card_id, 5)
        again = deck.get(card.card_id)
    assert reviewed is not None and again is not None
    assert again.interval_days == 1
    assert again.repetitions == 1


# ── Originals / Strong's ─────────────────────────────────────────────────


def test_built_in_psyche_present() -> None:
    e = get_strong_entry("G5590")
    assert e is not None and e.transliteration == "psychē"
    assert "soul" in " ".join(e.gloss_for("en")).lower()


def test_nephesh_has_spanish() -> None:
    e = get_strong_entry("H5315")
    assert "alma" in " ".join(e.gloss_for("es")).lower()


def test_register_dump_overrides() -> None:
    register_strong_dump(
        [
            StrongEntry(
                strong_number="H99999",
                transliteration="test",
                original="!",
                glosses={"en": ["test gloss"]},
            )
        ]
    )
    entry = get_strong_entry("H99999")
    assert entry is not None and entry.transliteration == "test"


def test_list_known_strongs_minimum_size() -> None:
    assert len(list_known_strongs()) >= 6
