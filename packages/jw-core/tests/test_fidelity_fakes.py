"""Tests for FakeNLI — the always-available deterministic provider.

Algorithm (per spec §"FakeNLI"):

  - verdict = "entails" iff Jaccard(words(claim), words(premise)) >= 0.8
  - verdict = "contradicts" iff a negation token appears in EXACTLY one of
    {claim, premise}: "no es" / "is not" / "não é"
  - else verdict = "neutral"
  - score = round(jaccard, 2)

The provider must be 100% pure (no network, no model files) and stable
across processes — ``evaluate("a", "b")`` returns the same NLIVerdict
forever.
"""

from __future__ import annotations

import pytest
from jw_core.fidelity import NLIProvider
from jw_core.fidelity.nli_providers.fakes import FakeNLI


@pytest.fixture()
def provider() -> FakeNLI:
    return FakeNLI()


def test_fake_implements_protocol(provider: FakeNLI) -> None:
    assert isinstance(provider, NLIProvider)
    assert provider.name == "fake-nli"
    assert provider.target == "cpu"
    assert provider.is_available() is True


def test_entails_when_claim_is_subset(provider: FakeNLI) -> None:
    v = provider.evaluate(
        claim="God loves the world",
        premise="God so loved the world that he gave his only Son",
    )
    assert v.verdict == "entails"
    assert v.score >= 0.5
    assert v.provider == "fake-nli"


def test_contradicts_on_asymmetric_negation_en(provider: FakeNLI) -> None:
    v = provider.evaluate(
        claim="The Trinity is biblical",
        premise="The Trinity is not biblical",
    )
    assert v.verdict == "contradicts"


def test_contradicts_on_asymmetric_negation_es(provider: FakeNLI) -> None:
    v = provider.evaluate(
        claim="el alma muere",
        premise="el alma no es inmortal",
    )
    assert v.verdict == "contradicts"


def test_contradicts_on_asymmetric_negation_pt(provider: FakeNLI) -> None:
    v = provider.evaluate(
        claim="Jesus é Deus",
        premise="Jesus não é Deus",
    )
    assert v.verdict == "contradicts"


def test_neutral_when_disjoint(provider: FakeNLI) -> None:
    v = provider.evaluate(
        claim="bananas are yellow",
        premise="the sky was blue today",
    )
    assert v.verdict == "neutral"
    assert v.score < 0.3


def test_deterministic_same_input_same_output(provider: FakeNLI) -> None:
    a = provider.evaluate(claim="hello world", premise="hello world today")
    b = provider.evaluate(claim="hello world", premise="hello world today")
    assert a == b


def test_score_is_clamped_in_unit_interval(provider: FakeNLI) -> None:
    v = provider.evaluate(claim="x", premise="x")
    assert 0.0 <= v.score <= 1.0


def test_empty_inputs_do_not_crash(provider: FakeNLI) -> None:
    v = provider.evaluate(claim="", premise="")
    assert v.verdict in {"entails", "neutral", "contradicts"}
    assert 0.0 <= v.score <= 1.0


def test_negation_in_both_does_not_count_as_contradiction(provider: FakeNLI) -> None:
    v = provider.evaluate(
        claim="el alma no es eterna",
        premise="el alma no es inmortal",
    )
    # both contain a negation → cancels out → verdict driven by jaccard only
    assert v.verdict in {"entails", "neutral"}
