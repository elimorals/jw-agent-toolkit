"""jw_core.verification.image_quote - defensive visual quote verifier (Fase 70).

Public API:
    from jw_core.verification.image_quote import (
        Verdict, ExtractedQuote, VisualFingerprint, MatchEvidence,
        ImageQuoteVerdict, verify_image_quote,
    )
"""

from __future__ import annotations

from jw_core.verification.image_quote.engine import verify_image_quote
from jw_core.verification.image_quote.models import (
    ExtractedQuote,
    ImageQuoteVerdict,
    MatchEvidence,
    Verdict,
    VisualFingerprint,
)

__all__ = [
    "ExtractedQuote",
    "ImageQuoteVerdict",
    "MatchEvidence",
    "Verdict",
    "VisualFingerprint",
    "verify_image_quote",
]
