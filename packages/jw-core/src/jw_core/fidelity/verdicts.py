"""NLIVerdict — the canonical output of every NLIProvider.

We use a frozen dataclass (not Pydantic) because ``jw-core`` deliberately
avoids Pydantic dependencies at the leaf layer — Pydantic lives one level
up in ``jw-eval`` / ``jw-agents``. Frozen dataclasses are hashable, fast,
and sufficient for our needs.

``ensure_verdict`` is the safe constructor every provider should funnel
through — it clamps ``score`` to [0, 1] and validates the verdict label.
This is the single chokepoint that protects downstream consumers from
provider bugs (LLM hallucinated ``score=1.7``, etc.).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Literal, get_args

Verdict = Literal["entails", "neutral", "contradicts"]
_VALID_VERDICTS: frozenset[str] = frozenset(get_args(Verdict))


@dataclass(frozen=True)
class NLIVerdict:
    """One NLI judgement, suitable for ``Finding.metadata["nli_*"]``.

    Fields:
      verdict   — discrete label (entails / neutral / contradicts).
      score     — confidence in [0, 1]. For multi-class providers, this is
                  the probability of the chosen verdict; for LLM judges,
                  the JSON-returned confidence.
      provider  — provider.name for traceability ("claude-nli", "deberta-v3-mnli",
                  "fake-nli", ...). The decorator stamps this into metadata.
      raw       — provider-specific debug payload. Optional. May be persisted
                  to traces (Fase 43) but is NEVER displayed in CLI output.
    """

    verdict: Verdict
    score: float
    provider: str
    raw: dict[str, Any] = field(default_factory=dict)


def ensure_verdict(
    *,
    verdict: str,
    score: float,
    provider: str,
    raw: dict[str, Any] | None = None,
) -> NLIVerdict:
    """Canonical constructor — clamp score, validate verdict label."""

    if verdict not in _VALID_VERDICTS:
        raise ValueError(
            f"invalid verdict {verdict!r}; expected one of {sorted(_VALID_VERDICTS)}"
        )
    score_f = float(score)
    if math.isnan(score_f):
        # Fail-closed: providers that hallucinate NaN (LLM bug) get the
        # most conservative score. ``min/max`` propagate NaN silently,
        # which would defeat the [0, 1] invariant downstream.
        score_f = 0.0
    clamped = max(0.0, min(1.0, score_f))
    return NLIVerdict(
        verdict=verdict,  # type: ignore[arg-type]
        score=clamped,
        provider=provider,
        raw=dict(raw) if raw else {},
    )


__all__ = ["NLIVerdict", "Verdict", "ensure_verdict"]
