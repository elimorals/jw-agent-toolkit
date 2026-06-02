"""Bridge to Fase 39 NLI runtime.

This module is import-safe even when Fase 39 (`jw_core.fidelity.nli`) is not
installed. Factories live in `factories.py`; here we only need a Protocol that
matches the Fase 39 provider shape so judges can be tested with fakes.
"""

from __future__ import annotations

import logging
import re
from typing import Protocol

logger = logging.getLogger(__name__)


class NLIVerdictLike(Protocol):
    """Matches `jw_core.fidelity.nli.EntailmentVerdict`."""

    verdict: str
    score: float


class NLIProviderLike(Protocol):
    """Matches `jw_core.fidelity.nli.NLIProvider`."""

    def evaluate_entailment(
        self, *, claim: str, premise: str
    ) -> NLIVerdictLike: ...


_QUOTE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"[“”]([^“”]{8,400})[“”]"),
    re.compile(r'"([^"]{8,400})"'),
    re.compile(r"«([^»]{8,400})»"),
)


def extract_premise_from_answer(answer: str) -> str | None:
    """Best-effort: extract the first quoted span in the answer as a premise."""

    if not answer:
        return None
    for pattern in _QUOTE_PATTERNS:
        m = pattern.search(answer)
        if m:
            premise = m.group(1).strip()
            if premise:
                return premise
    return None


def run_nli_check(
    *,
    answer: str,
    nli_provider: NLIProviderLike | None,
) -> tuple[str, float] | None:
    """Run NLI against (claim=answer, premise=quoted span)."""

    if nli_provider is None:
        return None
    premise = extract_premise_from_answer(answer)
    if premise is None:
        return None
    claim = answer
    try:
        verdict_obj = nli_provider.evaluate_entailment(
            claim=claim, premise=premise
        )
    except Exception as exc:
        logger.debug("NLI provider raised, skipping NLI stage: %s", exc)
        return None
    return (str(verdict_obj.verdict), float(verdict_obj.score))
