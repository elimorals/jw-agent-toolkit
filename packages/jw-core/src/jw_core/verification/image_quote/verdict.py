"""Verdict synthesis for the image-quote verifier (Fase 70).

Combines extracted quote, visual fingerprint, and RAG/NLI matches into
one of four verdicts:

  - SUPPORTED:     the image carries a real quote with no manipulation.
  - DISTORTED:     the quote is real but the image alters context / framing.
  - FABRICATED:    no matching source AND the visual fingerprint looks suspect.
  - UNVERIFIABLE:  no clear signal either way (e.g. low OCR quality).
"""

from __future__ import annotations

from jw_core.verification.image_quote.models import (
    ExtractedQuote,
    MatchEvidence,
    SuggestedAction,
    Verdict,
    VisualFingerprint,
)


def _action_for(verdict: Verdict) -> SuggestedAction:
    return {
        "SUPPORTED": "share_with_correct_link",
        "DISTORTED": "share_corrected_version",
        "FABRICATED": "do_not_share",
        "UNVERIFIABLE": "discuss_with_elders",
    }[verdict]


def synthesize_verdict(
    *,
    quote: ExtractedQuote,
    matches: list[MatchEvidence],
    fingerprint: VisualFingerprint,
) -> tuple[Verdict, float, str, SuggestedAction]:
    """Return (verdict, confidence, reasoning, suggested_action)."""

    anomalies = fingerprint.visual_anomalies
    has_anomalies = bool(anomalies)
    cleaned_len = len(quote.cleaned_quote.strip())

    # --- No matches at all -----------------------------------------------
    if not matches:
        if cleaned_len < 20:
            verdict: Verdict = "UNVERIFIABLE"
            confidence = 0.3
            reasoning = (
                "OCR did not produce a substantial quote; the image is "
                "not verifiable without clearer text."
            )
        elif has_anomalies:
            verdict = "FABRICATED"
            confidence = 0.7
            reasoning = (
                "No matches in the JW corpus AND visual anomalies "
                f"detected ({', '.join(anomalies)}). Likely fabricated."
            )
        else:
            verdict = "UNVERIFIABLE"
            confidence = 0.4
            reasoning = (
                "No source found in the indexed corpus; the image may be "
                "real but outside the index, or fabricated."
            )
        return (verdict, confidence, reasoning, _action_for(verdict))

    # --- We have at least one match -------------------------------------
    top = matches[0]
    if top.nli_verdict == "entails" and top.nli_score >= 0.85:
        if has_anomalies:
            verdict = "DISTORTED"
            confidence = 0.8
            reasoning = (
                "Text matches a real JW source, but the visual "
                f"presentation has anomalies ({', '.join(anomalies)})."
            )
        else:
            verdict = "SUPPORTED"
            confidence = min(top.nli_score, 0.95)
            reasoning = (
                "Quote textually matches a published JW source: "
                f"{top.source_url}"
            )
        return (verdict, confidence, reasoning, _action_for(verdict))

    if top.nli_verdict == "contradicts":
        verdict = "DISTORTED"
        confidence = 0.85
        reasoning = (
            "Closest match contradicts the quote text. Likely altered or "
            "decontextualized."
        )
        return (verdict, confidence, reasoning, _action_for(verdict))

    # entails but low score, or neutral
    verdict = "UNVERIFIABLE"
    confidence = 0.35
    reasoning = (
        f"Weak entailment (verdict={top.nli_verdict}, "
        f"score={top.nli_score:.2f}); cannot determine confidently."
    )
    return (verdict, confidence, reasoning, _action_for(verdict))
