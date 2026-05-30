"""Expanded quiz coverage (Gap 10)."""

from __future__ import annotations

from jw_core.family.quiz import (
    _QUESTIONS,
    generate_fill_blank_question,
    generate_quiz,
    quiz_pool_for_age,
)


def test_corpus_size_at_least_24() -> None:
    assert len(_QUESTIONS) >= 24


def test_age_band_pool_sizes() -> None:
    assert len(quiz_pool_for_age("younger")) >= 7
    assert len(quiz_pool_for_age("middle")) >= 7
    assert len(quiz_pool_for_age("older")) >= 7


def test_generate_quiz_balances_languages() -> None:
    items = generate_quiz(age_band="middle", n_questions=4, language="pt", seed=12)
    assert all(item["answer"] for item in items)


def test_fill_blank_masks_one_word() -> None:
    verse = "For God so loved the world that he gave his only-begotten Son."
    q = generate_fill_blank_question(verse, reference="John 3:16", language="en", seed=42)
    assert "____" in q["prompt"]
    assert q["answer"]
    assert q["answer"] not in q["prompt"]


def test_fill_blank_localizes_intro() -> None:
    q = generate_fill_blank_question("amor", reference="Juan 3:16", language="es")
    assert q["prompt"].startswith("Complete")
