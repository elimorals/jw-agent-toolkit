"""Personal study layer (Phase 14).

Surfaces:
  - reading_plan.py: Bible reading plans with daily tracking
  - personal_notes.py: per-verse notes persisted in SQLite, RAG-indexable
  - flashcards.py: spaced repetition over verses (SM-2 algorithm)
  - originals.py: Strong's numbers + interlinear hooks
"""

from jw_core.study.flashcards import (
    Flashcard,
    FlashcardDeck,
    review_card,
    schedule_next_review,
)
from jw_core.study.originals import (
    StrongEntry,
    get_strong_entry,
    list_known_strongs,
)
from jw_core.study.personal_notes import (
    PersonalNote,
    PersonalNoteStore,
    notes_to_rag_chunks,
)
from jw_core.study.reading_plan import (
    READING_PLANS,
    ReadingPlan,
    ReadingPlanTracker,
    list_reading_plans,
)

__all__ = [
    "READING_PLANS",
    "Flashcard",
    "FlashcardDeck",
    "PersonalNote",
    "PersonalNoteStore",
    "ReadingPlan",
    "ReadingPlanTracker",
    "StrongEntry",
    "get_strong_entry",
    "list_known_strongs",
    "list_reading_plans",
    "notes_to_rag_chunks",
    "review_card",
    "schedule_next_review",
]
