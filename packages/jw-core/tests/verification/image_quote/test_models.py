"""Image-quote verifier Pydantic models."""

from __future__ import annotations

import pytest

from jw_core.verification.image_quote.models import (
    ExtractedQuote,
    ImageQuoteVerdict,
    MatchEvidence,
    VisualFingerprint,
)


def test_visual_fingerprint_defaults() -> None:
    f = VisualFingerprint()
    assert f.apparent_era is None
    assert f.visual_anomalies == []
    assert f.layout_consistency == "unknown"


def test_extracted_quote_defaults_to_unknown_language() -> None:
    q = ExtractedQuote(raw_ocr_text="hi", cleaned_quote="hi")
    assert q.language_detected == "unknown"
    assert q.has_attribution is False


def test_match_evidence_rejects_out_of_range_nli_score() -> None:
    with pytest.raises(ValueError):
        MatchEvidence(
            source_url="x",
            source_text_original="x",
            nli_verdict="entails",
            nli_score=1.5,
        )


def test_image_quote_verdict_round_trip() -> None:
    v = ImageQuoteVerdict(
        image_path="/tmp/x.jpg",
        verdict="SUPPORTED",
        confidence=0.9,
        extracted_quote=ExtractedQuote(
            raw_ocr_text="x", cleaned_quote="x"
        ),
        visual_fingerprint=VisualFingerprint(),
        matches=[],
        reasoning="ok",
        suggested_action="share_with_correct_link",
    )
    dumped = v.model_dump()
    rehydrated = ImageQuoteVerdict.model_validate(dumped)
    assert rehydrated.verdict == "SUPPORTED"
    assert rehydrated.suggested_action == "share_with_correct_link"


def test_image_quote_verdict_rejects_unknown_action() -> None:
    with pytest.raises(ValueError):
        ImageQuoteVerdict(
            image_path="x",
            verdict="SUPPORTED",
            confidence=0.5,
            extracted_quote=ExtractedQuote(
                raw_ocr_text="x", cleaned_quote="x"
            ),
            visual_fingerprint=VisualFingerprint(),
            reasoning="x",
            suggested_action="burn_it",  # type: ignore[arg-type]
        )
