"""Tests for the advanced apologetics module (Module 9)."""

from __future__ import annotations

from jw_agents.apocrypha_detector import (
    _detect_framings,
    _extract_candidates,
    _verdict,
    ApocryphaCandidate,
)
from jw_agents.fact_checker import _judge


# ── fact_checker._judge tests ────────────────────────────────────────────


def test_judge_supported_with_official_urls() -> None:
    verdict = _judge(
        supporting=["https://wol.jw.org/x", "https://jw.org/y"],
        contradicting=[],
        require_published=True,
    )
    assert verdict.verdict == "SUPPORTED"
    assert verdict.confidence > 0.5


def test_judge_disputed_with_mixed_evidence() -> None:
    verdict = _judge(
        supporting=["https://wol.jw.org/x"],
        contradicting=["https://wol.jw.org/y"],
        require_published=True,
    )
    assert verdict.verdict == "DISPUTED"


def test_judge_rejected_when_only_contradictions() -> None:
    verdict = _judge(supporting=[], contradicting=["https://wol.jw.org/x"], require_published=True)
    assert verdict.verdict == "REJECTED"


def test_judge_unverifiable_when_nothing() -> None:
    verdict = _judge(supporting=[], contradicting=[], require_published=True)
    assert verdict.verdict == "UNVERIFIABLE"
    assert verdict.confidence == 0.0


def test_judge_downgrades_unpublished_only_to_disputed() -> None:
    verdict = _judge(
        supporting=["local-rag://chunk-42"],
        contradicting=[],
        require_published=True,
    )
    assert verdict.verdict == "DISPUTED"


def test_judge_supports_unpublished_when_allowed() -> None:
    verdict = _judge(
        supporting=["local-rag://chunk-42"],
        contradicting=[],
        require_published=False,
    )
    assert verdict.verdict == "SUPPORTED"


# ── apocrypha_detector logic (no network) ───────────────────────────────


def test_detect_framings_picks_up_watchtower_said() -> None:
    framings = _detect_framings("They told me the Watchtower said this is wrong.")
    assert framings and "watchtower said" in framings[0]


def test_extract_candidates_grabs_quoted_text() -> None:
    text = 'According to them, "this very long fake quote that exceeds twenty characters" appeared in 1980.'
    candidates = _extract_candidates(text, _detect_framings(text))
    assert candidates
    assert "very long fake quote" in candidates[0].quote


def test_verdict_apocryphal_when_framing_and_low_overlap() -> None:
    candidate = ApocryphaCandidate(
        quote="A made-up quote",
        framing="the watchtower said",
        confidence_genuine=0.05,
    )
    assert _verdict(candidate, min_confidence_genuine=0.55) == "APOCRYPHAL"


def test_verdict_genuine_when_high_overlap() -> None:
    candidate = ApocryphaCandidate(
        quote="Some real quote",
        framing="",
        confidence_genuine=0.9,
    )
    assert _verdict(candidate, min_confidence_genuine=0.55) == "GENUINE"


def test_verdict_suspicious_without_framing_and_low_overlap() -> None:
    candidate = ApocryphaCandidate(
        quote="Some quote",
        framing="",
        confidence_genuine=0.2,
    )
    assert _verdict(candidate, min_confidence_genuine=0.55) == "SUSPICIOUS"
