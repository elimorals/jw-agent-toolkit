"""Verdict synthesis tests (Fase 70)."""

from __future__ import annotations

from jw_core.verification.image_quote.models import (
    ExtractedQuote,
    MatchEvidence,
    VisualFingerprint,
)
from jw_core.verification.image_quote.verdict import synthesize_verdict


def _quote(text: str = "x" * 100) -> ExtractedQuote:
    return ExtractedQuote(raw_ocr_text=text, cleaned_quote=text)


def _short_quote() -> ExtractedQuote:
    return ExtractedQuote(raw_ocr_text="hi", cleaned_quote="hi")


def _match(verdict: str = "entails", score: float = 0.9) -> MatchEvidence:
    return MatchEvidence(
        source_url="https://wol.jw.org/x",
        source_pub_code="w23.04",
        source_text_original="...",
        nli_verdict=verdict,  # type: ignore[arg-type]
        nli_score=score,
    )


def test_supported_when_strong_match_no_anomalies() -> None:
    v, conf, reason, action = synthesize_verdict(
        quote=_quote(),
        matches=[_match("entails", 0.92)],
        fingerprint=VisualFingerprint(),
    )
    assert v == "SUPPORTED"
    assert conf >= 0.85
    assert action == "share_with_correct_link"
    assert "matches a published" in reason


def test_distorted_when_strong_match_but_anomalies() -> None:
    v, conf, reason, action = synthesize_verdict(
        quote=_quote(),
        matches=[_match("entails", 0.92)],
        fingerprint=VisualFingerprint(
            visual_anomalies=["font_mismatch"]
        ),
    )
    assert v == "DISTORTED"
    assert conf >= 0.7
    assert action == "share_corrected_version"


def test_distorted_when_contradicts() -> None:
    v, _, _, action = synthesize_verdict(
        quote=_quote(),
        matches=[_match("contradicts", 0.9)],
        fingerprint=VisualFingerprint(),
    )
    assert v == "DISTORTED"
    assert action == "share_corrected_version"


def test_fabricated_when_no_matches_and_anomalies() -> None:
    v, conf, reason, action = synthesize_verdict(
        quote=_quote(),
        matches=[],
        fingerprint=VisualFingerprint(
            visual_anomalies=["logo_modified"]
        ),
    )
    assert v == "FABRICATED"
    assert conf >= 0.6
    assert action == "do_not_share"
    assert "logo_modified" in reason


def test_unverifiable_when_no_matches_and_no_anomalies() -> None:
    v, _, _, action = synthesize_verdict(
        quote=_quote(),
        matches=[],
        fingerprint=VisualFingerprint(),
    )
    assert v == "UNVERIFIABLE"
    assert action == "discuss_with_elders"


def test_unverifiable_when_quote_too_short() -> None:
    v, conf, _, _ = synthesize_verdict(
        quote=_short_quote(),
        matches=[],
        fingerprint=VisualFingerprint(
            visual_anomalies=["font_mismatch"]
        ),
    )
    # Short quote always takes precedence -> UNVERIFIABLE
    assert v == "UNVERIFIABLE"
    assert conf <= 0.4


def test_unverifiable_when_weak_neutral_match() -> None:
    v, _, _, _ = synthesize_verdict(
        quote=_quote(),
        matches=[_match("neutral", 0.4)],
        fingerprint=VisualFingerprint(),
    )
    assert v == "UNVERIFIABLE"


def test_unverifiable_when_entails_but_low_score() -> None:
    v, _, _, _ = synthesize_verdict(
        quote=_quote(),
        matches=[_match("entails", 0.55)],
        fingerprint=VisualFingerprint(),
    )
    assert v == "UNVERIFIABLE"
