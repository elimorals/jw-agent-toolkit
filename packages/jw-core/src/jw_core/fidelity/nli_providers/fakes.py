"""Deterministic Fake NLI provider — no network, no model weights.

Algorithm:
  1. Tokenize both inputs (Unicode word chars, lowercased).
  2. Compute containment C = |claim_tokens ∩ premise_tokens| / |claim_tokens|
     (0 if claim_tokens is empty — vacuously unsupported).
     This measures "how much of the claim is found in the premise?", which
     is the natural NLI proxy: a claim is more entailed the more of its
     content appears in the premise.
  3. Detect explicit negation in each input (regex per language).
  4. If negation appears in exactly one input → verdict = "contradicts".
     If C >= 0.5 → verdict = "entails".
     Else → verdict = "neutral".
  5. score = round(C, 2), clamped to [0, 1] by ensure_verdict.

This is what every test in the test suite reaches for by default — the
factory falls back to it when no real provider is configured. It must
never raise on legal inputs and must be byte-identical across processes.
"""

from __future__ import annotations

import re

from jw_core.fidelity.nli import Target
from jw_core.fidelity.verdicts import NLIVerdict, ensure_verdict

# Regexes for explicit negation phrases. Conservative on purpose — false
# positives are worse than false negatives for a stub.
_NEGATION_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\bis\s+not\b", re.IGNORECASE),
    re.compile(r"\bare\s+not\b", re.IGNORECASE),
    re.compile(r"\bnever\b", re.IGNORECASE),
    re.compile(r"\bno\s+es\b", re.IGNORECASE),
    re.compile(r"\bno\s+son\b", re.IGNORECASE),
    re.compile(r"\bnunca\b", re.IGNORECASE),
    re.compile(r"\bnão\s+é\b", re.IGNORECASE),
    re.compile(r"\bnão\s+são\b", re.IGNORECASE),
)

_TOKEN_RE = re.compile(r"\w+", re.UNICODE)


def _words(text: str) -> frozenset[str]:
    return frozenset(_TOKEN_RE.findall(text.lower()))


def _containment(claim_tokens: frozenset[str], premise_tokens: frozenset[str]) -> float:
    """How much of the claim is supported by the premise.

    Returns ``|claim ∩ premise| / |claim|`` — 0.0 when ``claim`` is empty,
    1.0 when every claim token appears in the premise.
    """

    if not claim_tokens:
        return 0.0
    return len(claim_tokens & premise_tokens) / len(claim_tokens)


def _has_negation(text: str) -> bool:
    return any(p.search(text) for p in _NEGATION_PATTERNS)


class FakeNLI:
    """Pure-Python deterministic NLI. Always available."""

    name = "fake-nli"
    target: Target = "cpu"

    def is_available(self) -> bool:
        return True

    def evaluate(self, claim: str, premise: str, *, language: str = "en") -> NLIVerdict:
        wa, wb = _words(claim), _words(premise)
        cont = _containment(wa, wb)

        neg_claim = _has_negation(claim)
        neg_premise = _has_negation(premise)
        asymmetric_negation = neg_claim ^ neg_premise

        if asymmetric_negation:
            verdict = "contradicts"
        elif cont >= 0.5:
            verdict = "entails"
        else:
            verdict = "neutral"

        return ensure_verdict(
            verdict=verdict,
            score=round(cont, 2),
            provider=self.name,
            raw={
                "containment": round(cont, 4),
                "neg_claim": neg_claim,
                "neg_premise": neg_premise,
                "lang": language,
            },
        )


__all__ = ["FakeNLI"]
