"""Pydantic models for the image-quote verifier (Fase 70)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Verdict = Literal["SUPPORTED", "DISTORTED", "FABRICATED", "UNVERIFIABLE"]
SuggestedAction = Literal[
    "share_with_correct_link",
    "share_corrected_version",
    "do_not_share",
    "discuss_with_elders",
]
LayoutConsistency = Literal["consistent", "inconsistent", "unknown"]


class VisualFingerprint(BaseModel):
    apparent_era: str | None = None
    apparent_publication: str | None = None
    layout_consistency: LayoutConsistency = "unknown"
    visual_anomalies: list[str] = Field(default_factory=list)
    image_phash: str = ""
    image_format: str = ""
    image_size: tuple[int, int] = (0, 0)


class ExtractedQuote(BaseModel):
    raw_ocr_text: str
    cleaned_quote: str
    language_detected: Literal[
        "en", "es", "pt", "fr", "de", "unknown"
    ] = "unknown"
    has_attribution: bool = False
    attribution_text: str = ""


class MatchEvidence(BaseModel):
    source_url: str
    source_pub_code: str = ""
    source_text_original: str
    nli_verdict: Literal["entails", "neutral", "contradicts"]
    nli_score: float = Field(ge=0.0, le=1.0)
    diff_with_quote: str = ""


class ImageQuoteVerdict(BaseModel):
    image_path: str
    verdict: Verdict
    confidence: float = Field(ge=0.0, le=1.0)
    extracted_quote: ExtractedQuote
    visual_fingerprint: VisualFingerprint
    matches: list[MatchEvidence] = Field(default_factory=list)
    reasoning: str
    suggested_action: SuggestedAction
