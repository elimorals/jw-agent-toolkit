"""Property-based tests for the NLI providers.

Uses ``hypothesis`` (already a dev dep) to generate random text pairs and
assert invariants the providers MUST always honor:

  - verdict ∈ {"entails", "neutral", "contradicts"}
  - 0 ≤ score ≤ 1
  - provider == name
  - identical input → identical output (determinism, for FakeNLI)
  - swapping claim and premise can change the verdict but never break
    the type contract
"""

from __future__ import annotations

import math
import string

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from jw_core.fidelity.nli_providers.fakes import FakeNLI

# Restrict to printable ASCII to avoid byte-level issues in CI logs
_TEXT = st.text(
    alphabet=string.ascii_letters + string.digits + " .,;:!?",
    min_size=0,
    max_size=200,
)


@given(claim=_TEXT, premise=_TEXT)
@settings(max_examples=200, suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_fake_verdict_always_legal(claim: str, premise: str) -> None:
    v = FakeNLI().evaluate(claim=claim, premise=premise)
    assert v.verdict in {"entails", "neutral", "contradicts"}
    assert 0.0 <= v.score <= 1.0
    assert v.provider == "fake-nli"


@given(claim=_TEXT, premise=_TEXT)
@settings(max_examples=200)
def test_fake_is_deterministic(claim: str, premise: str) -> None:
    p = FakeNLI()
    assert p.evaluate(claim=claim, premise=premise) == p.evaluate(claim=claim, premise=premise)


@given(text=_TEXT.filter(lambda s: len(s) >= 4))
@settings(max_examples=100)
def test_fake_self_entailment_is_high(text: str) -> None:
    v = FakeNLI().evaluate(claim=text, premise=text)
    # When claim == premise, containment = 1.0 unless tokenization is empty
    # (all-punctuation/whitespace input). In that edge case verdict is neutral.
    assert v.score >= 0.99 or v.verdict == "neutral"


@given(
    claim=_TEXT,
    premise=_TEXT,
    language=st.sampled_from(["en", "es", "pt", "fr", "de"]),
)
@settings(max_examples=200)
def test_language_does_not_break_fake(claim: str, premise: str, language: str) -> None:
    v = FakeNLI().evaluate(claim=claim, premise=premise, language=language)
    assert v.raw["lang"] == language


@given(claim=_TEXT, premise=_TEXT)
@settings(max_examples=200)
def test_swap_preserves_type_contract(claim: str, premise: str) -> None:
    p = FakeNLI()
    a = p.evaluate(claim=claim, premise=premise)
    b = p.evaluate(claim=premise, premise=claim)
    # both legal verdicts
    assert a.verdict in {"entails", "neutral", "contradicts"}
    assert b.verdict in {"entails", "neutral", "contradicts"}
    # scores both in [0, 1]
    assert 0.0 <= a.score <= 1.0
    assert 0.0 <= b.score <= 1.0


@given(claim=_TEXT, premise=_TEXT)
@settings(max_examples=50)
def test_score_is_finite(claim: str, premise: str) -> None:
    v = FakeNLI().evaluate(claim=claim, premise=premise)
    assert math.isfinite(v.score)
