"""Tests for the GRPO reward functions.

We can't easily test the trainer itself without a GPU, but we CAN test
that the reward functions return sensible scores on fixture completions.
"""

from __future__ import annotations

from jw_finetune.train.grpo import (
    composite_reward,
    make_citation_reward,
    make_length_penalty,
    make_terminology_reward,
)


def test_citation_reward_basic() -> None:
    fn = make_citation_reward()
    prompts = ["q1", "q2"]
    completions = [
        "Como dice Mateo 24:14, esto es una señal.",   # has ref
        "No tiene ninguna cita bíblica.",                # no ref
    ]
    scores = fn(prompts, completions)
    assert scores == [1.0, 0.0]


def test_citation_reward_threshold() -> None:
    fn = make_citation_reward(expect_at_least=2)
    completions = ["Solo una: Mateo 24:14"]
    assert fn(["q"], completions) == [0.0]
    completions = ["Dos: Mateo 24:14 y Hechos 1:8"]
    assert fn(["q"], completions) == [1.0]


def test_terminology_reward_es() -> None:
    fn = make_terminology_reward(language="es")
    completions = [
        "Jehová es el Soberano del universo.",
        "Un texto sin terminología relevante.",
    ]
    scores = fn(["q1", "q2"], completions)
    assert scores == [1.0, 0.0]


def test_length_penalty_in_range() -> None:
    fn = make_length_penalty(min_chars=30, max_chars=200)
    completions = [
        "x" * 100,   # in range
        "x" * 10,    # too short
        "x" * 500,   # too long
    ]
    scores = fn(["q"] * 3, completions)
    assert scores[0] == 1.0
    assert 0 < scores[1] < 1.0  # linear penalty
    assert scores[2] < 1.0  # over-length penalty
    assert all(0.0 <= s <= 1.0 for s in scores)


def test_composite_reward() -> None:
    fn = composite_reward(
        [make_citation_reward(), make_terminology_reward(language="es")],
        weights=[0.7, 0.3],
    )
    completions = [
        "Jehová mencionó en Mateo 24:14 que el Reino vendrá.",  # both 1.0
        "Sin referencia ni terminología.",  # both 0.0
    ]
    scores = fn(["q1", "q2"], completions)
    assert scores[0] == 1.0  # 0.7 + 0.3
    assert scores[1] == 0.0


def test_composite_weight_mismatch_raises() -> None:
    import pytest
    with pytest.raises(ValueError, match="weights"):
        composite_reward([make_citation_reward()], weights=[0.5, 0.5])
