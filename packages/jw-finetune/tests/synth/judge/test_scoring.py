"""Tests for the transparent scoring formula.

Formula (spec Fase 44):
    base = 4.0
    + 1.5 if cites_jw_publication
    + 1.5 if has_minimum_substance
    + 2.0 * nli_score if nli_verdict == "entails"
    - 3.0 if nli_verdict == "contradicts"
    + pedagogical_quality (0..3)
    clamp [0, 10]

When a signal is None (stage didn't run), it contributes neutral 0.0.
"""

from __future__ import annotations

import pytest

from jw_finetune.synth.judge.scoring import compute_overall


def test_baseline_no_signals() -> None:
    s = compute_overall(
        cites=False,
        substance=False,
        nli_verdict=None,
        nli_score=None,
        pedagogical=None,
    )
    assert s == pytest.approx(4.0)


def test_full_pass_signals_clamped_at_10() -> None:
    s = compute_overall(
        cites=True,
        substance=True,
        nli_verdict="entails",
        nli_score=0.95,
        pedagogical=3,
    )
    assert s == 10.0


def test_heuristic_only_loose_pass() -> None:
    s = compute_overall(
        cites=True,
        substance=True,
        nli_verdict=None,
        nli_score=None,
        pedagogical=None,
    )
    assert s == pytest.approx(7.0)


def test_contradicts_penalizes_three_points() -> None:
    s = compute_overall(
        cites=True,
        substance=True,
        nli_verdict="contradicts",
        nli_score=0.85,
        pedagogical=None,
    )
    assert s == pytest.approx(4.0)


def test_neutral_verdict_contributes_zero_from_nli() -> None:
    s = compute_overall(
        cites=True,
        substance=True,
        nli_verdict="neutral",
        nli_score=0.42,
        pedagogical=2,
    )
    assert s == pytest.approx(9.0)


def test_pedagogical_zero_is_distinct_from_none() -> None:
    s_zero = compute_overall(
        cites=True,
        substance=True,
        nli_verdict=None,
        nli_score=None,
        pedagogical=0,
    )
    s_none = compute_overall(
        cites=True,
        substance=True,
        nli_verdict=None,
        nli_score=None,
        pedagogical=None,
    )
    assert s_zero == s_none == pytest.approx(7.0)


def test_clamps_at_zero_floor() -> None:
    s = compute_overall(
        cites=False,
        substance=False,
        nli_verdict="contradicts",
        nli_score=0.99,
        pedagogical=0,
    )
    assert s == pytest.approx(1.0)


def test_pedagogical_only_signal() -> None:
    s = compute_overall(
        cites=False,
        substance=False,
        nli_verdict=None,
        nli_score=None,
        pedagogical=3,
    )
    assert s == pytest.approx(7.0)


def test_entails_with_low_nli_score_small_bonus() -> None:
    s = compute_overall(
        cites=True,
        substance=True,
        nli_verdict="entails",
        nli_score=0.30,
        pedagogical=None,
    )
    assert s == pytest.approx(7.6)
