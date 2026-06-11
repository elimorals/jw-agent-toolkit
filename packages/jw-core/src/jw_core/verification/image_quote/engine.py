"""End-to-end engine for the image-quote verifier (Fase 70).

Pipeline:
    load_image -> ocr -> cleanup -> extract_quote -> fingerprint
       -> RAG retrieval (inject) -> NLI verify (inject) -> verdict

RAG retrieval and NLI providers are inyectables Protocol-shaped so tests
can run without network or large models. Production wires the real RAG
store (F33) and the F39 NLI factory; if either is absent, the engine
degrades to UNVERIFIABLE rather than crashing.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import Any, Protocol

from jw_core.verification.image_quote.extractor import extract_quote
from jw_core.verification.image_quote.fingerprint import (
    assess_layout_consistency,
    detect_apparent_era,
    detect_apparent_publication,
    detect_visual_anomalies,
)
from jw_core.verification.image_quote.models import (
    ExtractedQuote,
    ImageQuoteVerdict,
    MatchEvidence,
    VisualFingerprint,
)
from jw_core.verification.image_quote.ocr_cleanup import (
    cleanup_ocr_text,
    ocr_image,
)
from jw_core.verification.image_quote.preprocess import load_image
from jw_core.verification.image_quote.verdict import synthesize_verdict

logger = logging.getLogger(__name__)


class RAGHit(Protocol):
    """Minimal shape a RAG hit must expose for the verifier."""

    source_url: str
    source_pub_code: str
    source_text_original: str


RAGRetriever = Callable[[str], Awaitable[list[RAGHit]]]


class NLILike(Protocol):
    def evaluate_entailment(
        self, *, claim: str, premise: str
    ) -> Any: ...


async def _no_retriever(_q: str) -> list[Any]:
    return []


def _build_matches(
    *,
    quote: ExtractedQuote,
    hits: list[Any],
    nli: NLILike | None,
) -> list[MatchEvidence]:
    matches: list[MatchEvidence] = []
    for hit in hits:
        source_text = getattr(hit, "source_text_original", "")
        if not source_text:
            continue
        verdict_label: str = "neutral"
        score: float = 0.0
        if nli is not None:
            try:
                v = nli.evaluate_entailment(
                    claim=quote.cleaned_quote, premise=source_text
                )
                verdict_label = str(getattr(v, "verdict", "neutral"))
                raw = getattr(v, "score", None)
                if isinstance(raw, (int, float)):
                    score = float(raw)
            except Exception as exc:  # noqa: BLE001
                logger.debug("verify NLI raised %s; using neutral.", exc)
                verdict_label = "neutral"
        if verdict_label not in ("entails", "neutral", "contradicts"):
            verdict_label = "neutral"
        matches.append(
            MatchEvidence(
                source_url=getattr(hit, "source_url", ""),
                source_pub_code=getattr(hit, "source_pub_code", ""),
                source_text_original=source_text,
                nli_verdict=verdict_label,  # type: ignore[arg-type]
                nli_score=max(0.0, min(1.0, score)),
            )
        )
    return matches


async def verify_image_quote(
    image_path: str,
    *,
    language: str = "es",
    retriever: RAGRetriever | None = None,
    nli: NLILike | None = None,
    ocr_text_override: str | None = None,
    vlm_description: str = "",
    use_real_defaults: bool = False,
) -> ImageQuoteVerdict:
    """Full pipeline. `ocr_text_override` lets tests bypass Tesseract.

    When `use_real_defaults` is True and `retriever`/`nli` are not
    provided, the engine wires the F33 RAG store (via
    `JW_IMAGE_QUOTE_STORE_PATH`) and the F39 NLI factory; missing
    components degrade silently to UNVERIFIABLE.
    """

    pil_image, meta = load_image(image_path)
    raw = (
        ocr_text_override
        if ocr_text_override is not None
        else ocr_image(pil_image, language=language)
    )
    cleaned = cleanup_ocr_text(raw)
    quote = extract_quote(cleaned)

    fingerprint = VisualFingerprint(
        apparent_era=detect_apparent_era(vlm_description, cleaned),
        apparent_publication=detect_apparent_publication(
            vlm_description, cleaned
        ),
        layout_consistency=assess_layout_consistency(
            vlm_description, cleaned
        ),  # type: ignore[arg-type]
        visual_anomalies=detect_visual_anomalies(
            vlm_description, cleaned
        ),
        image_phash=meta.get("phash", ""),
        image_format=meta.get("format", ""),
        image_size=meta.get("size", (0, 0)),
    )

    resolved_retriever = retriever
    resolved_nli = nli
    if use_real_defaults:
        if resolved_retriever is None:
            from jw_core.verification.image_quote.factories import (
                default_rag_retriever,
            )

            resolved_retriever = default_rag_retriever()
        if resolved_nli is None:
            from jw_core.verification.image_quote.factories import (
                default_nli,
            )

            resolved_nli = default_nli(language=language)

    retrieve = resolved_retriever or _no_retriever
    try:
        hits = await retrieve(quote.cleaned_quote)
    except Exception as exc:  # noqa: BLE001
        logger.warning("verify_image_quote retriever raised: %s", exc)
        hits = []

    matches = _build_matches(quote=quote, hits=hits, nli=resolved_nli)
    verdict, confidence, reasoning, suggested_action = synthesize_verdict(
        quote=quote, matches=matches, fingerprint=fingerprint
    )

    return ImageQuoteVerdict(
        image_path=image_path,
        verdict=verdict,
        confidence=confidence,
        extracted_quote=quote,
        visual_fingerprint=fingerprint,
        matches=matches,
        reasoning=reasoning,
        suggested_action=suggested_action,
    )
