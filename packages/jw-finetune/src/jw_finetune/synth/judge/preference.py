"""Preference verdict — turn the per-sample Judge into a pairwise annotator.

This is the bridge between the existing single-sample judge (`score_qa_pair`)
and the RLAIF dataset generator (`jw_finetune.synth.preference`).

Design choice: we deliberately do NOT introduce a new "preference mode"
to the Judge. The pairwise scoring is just two calls to `score_qa_pair`
plus a small comparison protocol that respects:
  1. Hard-fail asymmetry: if one answer is rejected for a hard reason
     (no_jw_citation, nli_contradicts) and the other isn't, that
     decides the pair unambiguously.
  2. Principle violations (regex tier) act as hard fails too.
  3. Otherwise compare `overall` scores; ties resolved by NLI score
     if both have one, else "tie".

The result is `PreferenceVerdict(winner, margin, reasons)`. `margin` is
absolute difference in `overall`; downstream RLAIF can filter out
low-margin pairs to keep the DPO dataset clean.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from jw_finetune.synth.judge.models import QAScore

Winner = Literal["a", "b", "tie"]

# Reasons that are doctrinally fatal — a sample with any of these
# automatically loses against a sample without them.
_HARD_FAIL_CODES: frozenset[str] = frozenset(
    {
        "nli_contradicts",
        "no_jw_citation",
        "principle_hard_violation",
    }
)


class PreferenceVerdict(BaseModel):
    """Pairwise comparison result. `margin` is |overall_a - overall_b|."""

    winner: Winner
    margin: float = Field(ge=0.0)
    reasons: list[str] = Field(default_factory=list)
    score_a: float = Field(ge=0.0, le=10.0)
    score_b: float = Field(ge=0.0, le=10.0)


def _has_hard_fail(score: QAScore) -> bool:
    return any(r.code in _HARD_FAIL_CODES for r in score.reasons)


def compare_scores(
    score_a: QAScore,
    score_b: QAScore,
    *,
    tie_epsilon: float = 0.05,
) -> PreferenceVerdict:
    """Compare two QAScores and produce a PreferenceVerdict.

    Decision rules, in order:
      1. If exactly one of (a, b) has a hard fail → the other wins.
      2. If both kept == False with different reasons → still compare overall.
      3. Compare overall, with `tie_epsilon` slack to avoid spurious wins.
      4. NLI score breaks remaining ties when both have one.
    """

    reasons: list[str] = []
    margin = abs(score_a.overall - score_b.overall)

    hard_a = _has_hard_fail(score_a)
    hard_b = _has_hard_fail(score_b)

    if hard_a and not hard_b:
        reasons.append("a has hard fail")
        return PreferenceVerdict(
            winner="b",
            margin=margin,
            reasons=reasons,
            score_a=score_a.overall,
            score_b=score_b.overall,
        )
    if hard_b and not hard_a:
        reasons.append("b has hard fail")
        return PreferenceVerdict(
            winner="a",
            margin=margin,
            reasons=reasons,
            score_a=score_a.overall,
            score_b=score_b.overall,
        )

    if margin <= tie_epsilon:
        # Both within slack — let NLI break it if available.
        if (
            score_a.nli_score is not None
            and score_b.nli_score is not None
            and abs(score_a.nli_score - score_b.nli_score) > tie_epsilon
        ):
            if score_a.nli_score > score_b.nli_score:
                reasons.append("nli tiebreak: a")
                winner: Winner = "a"
            else:
                reasons.append("nli tiebreak: b")
                winner = "b"
            return PreferenceVerdict(
                winner=winner,
                margin=margin,
                reasons=reasons,
                score_a=score_a.overall,
                score_b=score_b.overall,
            )
        reasons.append(f"overall within ε={tie_epsilon}")
        return PreferenceVerdict(
            winner="tie",
            margin=margin,
            reasons=reasons,
            score_a=score_a.overall,
            score_b=score_b.overall,
        )

    if score_a.overall > score_b.overall:
        reasons.append(f"overall a > b by {margin:.2f}")
        return PreferenceVerdict(
            winner="a",
            margin=margin,
            reasons=reasons,
            score_a=score_a.overall,
            score_b=score_b.overall,
        )
    reasons.append(f"overall b > a by {margin:.2f}")
    return PreferenceVerdict(
        winner="b",
        margin=margin,
        reasons=reasons,
        score_a=score_a.overall,
        score_b=score_b.overall,
    )
