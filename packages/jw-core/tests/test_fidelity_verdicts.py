"""Tests for jw_core.fidelity.verdicts.

The dataclass is frozen (hashable) and serializable via ``asdict``. The
Verdict Literal is exhaustive: only three labels are legal, anything else
must trip a runtime guard.
"""

from __future__ import annotations

from dataclasses import asdict, is_dataclass
from typing import get_args

import pytest
from jw_core.fidelity.verdicts import NLIVerdict, Verdict, ensure_verdict


def test_verdict_literal_has_three_values() -> None:
    assert set(get_args(Verdict)) == {"entails", "neutral", "contradicts"}


def test_nli_verdict_is_frozen_dataclass() -> None:
    v = NLIVerdict(verdict="entails", score=0.92, provider="fake-nli", raw={})
    assert is_dataclass(v)
    with pytest.raises(Exception):  # FrozenInstanceError subclass of AttributeError
        v.score = 0.5  # type: ignore[misc]


def test_nli_verdict_asdict_roundtrips() -> None:
    v = NLIVerdict(
        verdict="contradicts",
        score=0.71,
        provider="claude-nli",
        raw={"reason": "negation"},
    )
    d = asdict(v)
    assert d == {
        "verdict": "contradicts",
        "score": 0.71,
        "provider": "claude-nli",
        "raw": {"reason": "negation"},
    }


def test_nli_verdict_clamps_score_in_constructor_via_ensure() -> None:
    # ensure_verdict is the canonical safe constructor used by providers
    v = ensure_verdict(verdict="entails", score=1.7, provider="x")
    assert v.score == 1.0
    v2 = ensure_verdict(verdict="entails", score=-0.3, provider="x")
    assert v2.score == 0.0


def test_ensure_verdict_rejects_bad_label() -> None:
    with pytest.raises(ValueError, match="invalid verdict"):
        ensure_verdict(verdict="maybe", score=0.5, provider="x")  # type: ignore[arg-type]


def test_ensure_verdict_default_raw_is_empty_dict() -> None:
    v = ensure_verdict(verdict="neutral", score=0.5, provider="x")
    assert v.raw == {}


def test_ensure_verdict_maps_nan_to_zero() -> None:
    """NaN score from a buggy provider must not break the [0, 1] invariant.

    ``min/max`` propagate NaN, so a naive clamp would leave NaN in place.
    ensure_verdict is the single chokepoint that guarantees finite scores.
    """

    v = ensure_verdict(verdict="entails", score=float("nan"), provider="x")
    assert v.score == 0.0
    assert v.verdict == "entails"
