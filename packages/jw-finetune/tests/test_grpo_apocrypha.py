"""Tests for the apocrypha penalty reward."""

from __future__ import annotations

from jw_finetune.train.grpo import make_apocrypha_penalty


def test_apocrypha_penalty_clean_text() -> None:
    fn = make_apocrypha_penalty()
    answers = [
        "Como dice Mateo 24:14, el Reino traerá paz.",
        "Hechos 1:8 menciona la obra mundial.",
    ]
    scores = fn(["q1", "q2"], answers)
    assert scores == [1.0, 1.0]


def test_apocrypha_penalty_returns_neutral_when_detector_missing(monkeypatch) -> None:
    """If the apocrypha_detector module isn't importable, return 1.0 for safety."""
    import sys

    # Hide the agent module
    monkeypatch.setitem(sys.modules, "jw_agents.apocrypha_detector", None)
    fn = make_apocrypha_penalty()
    answers = ["whatever text"]
    # Should still return a score per completion
    scores = fn(["q"], answers)
    assert len(scores) == 1
    assert scores[0] == 1.0


def test_apocrypha_penalty_returns_per_completion() -> None:
    fn = make_apocrypha_penalty()
    answers = ["a", "b", "c"]
    scores = fn(["q"] * 3, answers)
    assert len(scores) == 3
