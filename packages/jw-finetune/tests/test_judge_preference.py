"""Tests for the pairwise judge — Judge.score_pair() and compare_scores()."""

from __future__ import annotations

from jw_finetune.synth.judge.models import QAScore, RejectionReason
from jw_finetune.synth.judge.preference import compare_scores


def _score(overall: float, *, kept: bool = True, reasons: list[str] | None = None) -> QAScore:
    return QAScore(
        cites_jw_publication=kept,
        has_minimum_substance=True,
        overall=overall,
        kept=kept,
        reasons=[RejectionReason(code=c) for c in (reasons or [])],  # type: ignore[arg-type]
    )


def test_hard_fail_decides_pair_against_loser() -> None:
    a = _score(8.0, kept=False, reasons=["nli_contradicts"])
    b = _score(6.0)
    v = compare_scores(a, b)
    assert v.winner == "b"
    assert "hard fail" in " ".join(v.reasons)


def test_hard_fail_both_sides_falls_back_to_overall() -> None:
    a = _score(7.0, kept=False, reasons=["nli_contradicts"])
    b = _score(5.0, kept=False, reasons=["principle_hard_violation"])
    v = compare_scores(a, b)
    # Both have hard fails → comparison defers to overall.
    assert v.winner == "a"


def test_clear_margin_picks_higher_overall() -> None:
    v = compare_scores(_score(8.0), _score(5.0))
    assert v.winner == "a"
    assert v.margin == 3.0


def test_within_epsilon_is_tie_when_no_nli() -> None:
    v = compare_scores(_score(5.0), _score(5.02))
    assert v.winner == "tie"


def test_nli_breaks_tie_when_within_epsilon() -> None:
    a = QAScore(
        cites_jw_publication=True,
        has_minimum_substance=True,
        nli_score=0.9,
        nli_verdict="entails",
        overall=5.0,
        kept=True,
    )
    b = QAScore(
        cites_jw_publication=True,
        has_minimum_substance=True,
        nli_score=0.4,
        nli_verdict="neutral",
        overall=5.01,
        kept=True,
    )
    v = compare_scores(a, b, tie_epsilon=0.1)
    assert v.winner == "a"
    assert "nli tiebreak" in " ".join(v.reasons)


def test_no_jw_citation_is_a_hard_fail() -> None:
    a = _score(6.0, kept=False, reasons=["no_jw_citation"])
    b = _score(4.0)
    v = compare_scores(a, b)
    # The cite-less answer loses despite higher overall.
    assert v.winner == "b"


def test_principle_hard_violation_is_recognized_as_hard_fail() -> None:
    a = _score(9.0, kept=False, reasons=["principle_hard_violation"])
    b = _score(7.0)
    v = compare_scores(a, b)
    assert v.winner == "b"


def test_low_overall_below_threshold_alone_is_not_hard_fail() -> None:
    """`overall_below_threshold` is a soft reason — comparison still uses overall."""
    a = _score(2.0, kept=False, reasons=["overall_below_threshold"])
    b = _score(8.0)
    v = compare_scores(a, b)
    # The "kept=False" side with lower overall just loses on overall;
    # but if both have only soft fails, we treat them symmetrically.
    assert v.winner == "b"
