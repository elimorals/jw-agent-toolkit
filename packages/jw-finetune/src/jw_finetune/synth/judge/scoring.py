"""Transparent scoring formula for the synth judge.

The formula is intentionally NOT a black box — every coefficient is named,
auditable, and unit-tested. It does not "learn" from data; if we want to
re-weight in the future, this is the single file to edit.
"""

from __future__ import annotations

from jw_finetune.synth.judge.models import NLIVerdict

_BASE = 4.0
_W_CITES = 1.5
_W_SUBSTANCE = 1.5
_W_NLI_ENTAILS = 2.0
_W_NLI_CONTRADICTS = -3.0

_FLOOR = 0.0
_CEIL = 10.0


def compute_overall(
    *,
    cites: bool,
    substance: bool,
    nli_verdict: NLIVerdict | None,
    nli_score: float | None,
    pedagogical: int | None,
) -> float:
    """Combine the per-stage signals into an `overall` in [0, 10]."""

    score = _BASE
    if cites:
        score += _W_CITES
    if substance:
        score += _W_SUBSTANCE
    if nli_verdict == "entails" and nli_score is not None:
        score += _W_NLI_ENTAILS * nli_score
    elif nli_verdict == "contradicts":
        score += _W_NLI_CONTRADICTS
    if pedagogical is not None:
        score += float(pedagogical)
    if score < _FLOOR:
        return _FLOOR
    if score > _CEIL:
        return _CEIL
    return score
