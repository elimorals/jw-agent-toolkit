"""Pydantic models for the synth judge.

A QAScore is the verdict of running the 3-stage judge on a single Q&A pair.
- Heuristic flags (`cites_jw_publication`, `has_minimum_substance`) are always
  populated.
- `nli_score`/`nli_verdict` are populated only when the NLI provider is wired
  and the answer contains a verifiable claim/premise.
- `pedagogical_quality` is populated only when the LLM judge is wired.
- `overall` is the transparent weighted sum in [0, 10] (formula in scoring.py).
- `kept` is the final decision after applying the configured cutoff.
- `reasons` lists the structured rejection reasons (empty if kept).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

RejectionCode = Literal[
    "no_jw_citation",
    "insufficient_substance",
    "nli_contradicts",
    "nli_neutral_low",
    "pedagogical_low",
    "overall_below_threshold",
]

NLIVerdict = Literal["entails", "neutral", "contradicts"]


class RejectionReason(BaseModel):
    """Why a pair was discarded by the judge."""

    code: RejectionCode
    detail: str = ""


class QAScore(BaseModel):
    """Score returned by the judge for one Q&A pair."""

    cites_jw_publication: bool
    has_minimum_substance: bool
    nli_score: float | None = Field(default=None, ge=0.0, le=1.0)
    nli_verdict: NLIVerdict | None = None
    pedagogical_quality: int | None = Field(default=None, ge=0, le=3)
    overall: float = Field(ge=0.0, le=10.0)
    kept: bool
    reasons: list[RejectionReason] = Field(default_factory=list)
