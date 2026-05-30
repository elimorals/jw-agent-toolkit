"""Tests for the family + children module (Module 5)."""

from __future__ import annotations

from datetime import date

from jw_core.family.family_worship import (
    plan_family_worship,
    suggest_topics_for_age,
)
from jw_core.family.kids_resources import (
    GREAT_TEACHER_LESSONS,
    LESSON_BY_TOPIC,
    list_lessons_for_age,
    pick_lesson_by_topic,
)
from jw_core.family.quiz import generate_quiz, quiz_pool_for_age


# ── Lessons ──────────────────────────────────────────────────────────────


def test_lesson_catalog_non_empty() -> None:
    assert len(GREAT_TEACHER_LESSONS) >= 8


def test_lesson_by_topic_lookup() -> None:
    lesson = pick_lesson_by_topic("ransom", language="en")
    assert lesson is not None
    assert lesson["title"].startswith("Why Did Jesus")
    assert "John 3:16" in lesson["scripture_anchors"]


def test_list_lessons_for_younger_returns_age_appropriate() -> None:
    items = list_lessons_for_age("younger", language="es")
    assert items
    for it in items:
        assert "younger" in it["age_bands"]


def test_lesson_by_topic_unknown_returns_none() -> None:
    assert pick_lesson_by_topic("unknownXYZ") is None


# ── Family worship ──────────────────────────────────────────────────────


def test_suggest_topics_fallback_to_middle() -> None:
    middle = suggest_topics_for_age("unknown")
    assert middle == suggest_topics_for_age("middle")


def test_plan_family_worship_for_four_weeks() -> None:
    plans = plan_family_worship(
        weeks=4,
        start_date="2026-06-01",
        age_band="middle",
        language="es",
    )
    assert len(plans) == 4
    # Weeks must be 7 days apart
    dates = [date.fromisoformat(p.week_of) for p in plans]
    deltas = [(dates[i + 1] - dates[i]).days for i in range(3)]
    assert all(d == 7 for d in deltas)
    # All plans have a theme + activity hook
    for p in plans:
        assert p.theme
        assert p.activity_hook
    # Suggested songs should map at least once
    assert any(p.song_suggestion is not None for p in plans)


def test_plan_family_worship_topic_overrides_kept() -> None:
    plans = plan_family_worship(
        weeks=2,
        age_band="middle",
        topic_overrides=["love"],
        language="en",
    )
    assert all("How Can You Show Love" in p.theme or p.main_lesson.topic == "love" for p in plans)


def test_plan_family_worship_to_dict_shape() -> None:
    plan = plan_family_worship(weeks=1, age_band="younger", language="en")[0]
    d = plan.to_dict()
    assert "lesson_chapter" in d
    assert d["main_scripture"]


# ── Quiz ─────────────────────────────────────────────────────────────────


def test_pool_for_age_returns_only_age_questions() -> None:
    questions = quiz_pool_for_age("younger")
    assert questions
    assert all(q.age_band == "younger" for q in questions)


def test_generate_quiz_deterministic_with_seed() -> None:
    a = generate_quiz(age_band="middle", n_questions=3, language="es", seed=42)
    b = generate_quiz(age_band="middle", n_questions=3, language="es", seed=42)
    assert a == b


def test_generate_quiz_respects_count() -> None:
    items = generate_quiz(age_band="older", n_questions=2, language="en", seed=1)
    assert len(items) == 2
    for it in items:
        assert "answer" in it
        assert "prompt" in it
        assert it["scripture_ref"]
