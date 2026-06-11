"""Quote extraction from cleaned OCR text (Fase 70).

Identifies the main "quote-like" span, detects rough language, and
parses any attribution (e.g. "Atalaya, abril 2024" or "w23.04 p. 5").
"""

from __future__ import annotations

import re

from jw_core.verification.image_quote.models import ExtractedQuote

# Compiled patterns
_PUB_CODE = re.compile(
    r"\b("
    r"w\d{2,}|ws\d{2,}|wp\d{2,}|g\d{2,}|jt|bh|sjj|jy|rs|it|"
    r"km\d{2,}|yb\d{2,}|cl|lff"
    r")(\.\d+)?\b",
    re.IGNORECASE,
)

_PUB_TITLE = re.compile(
    r"\b(Atalaya|Watchtower|Despertad|Awake!|Sentinela)\b"
    r"[, ]*(.{0,40}?(20\d{2}|19\d{2}))?",
)

_WOL_URL = re.compile(r"https?://(?:www\.)?wol\.jw\.org/\S+", re.IGNORECASE)

_LANG_HINT_WORDS: dict[str, frozenset[str]] = {
    "es": frozenset({"que", "para", "como", "porque", "según", "jehová"}),
    "en": frozenset({"that", "with", "from", "because", "jehovah"}),
    "pt": frozenset({"que", "para", "como", "porque", "segundo", "jeová"}),
}


def detect_language(text: str) -> str:
    """Cheap language sniffer over hint words. Returns 'unknown' on low signal."""

    if not text:
        return "unknown"
    lowered = text.lower()
    scores: dict[str, int] = {}
    for lang, words in _LANG_HINT_WORDS.items():
        scores[lang] = sum(1 for w in words if w in lowered)
    best = max(scores.items(), key=lambda kv: kv[1])
    if best[1] == 0:
        return "unknown"
    # Require a small lead over runners-up to avoid es/pt cognate noise.
    runners = sorted(scores.values(), reverse=True)
    if len(runners) > 1 and runners[0] - runners[1] < 1:
        return "unknown"
    return best[0]


def _extract_attribution(text: str) -> tuple[bool, str]:
    """Return (has_attribution, attribution_text)."""

    matches: list[str] = []
    for pat in (_WOL_URL, _PUB_CODE, _PUB_TITLE):
        for m in pat.finditer(text):
            span = m.group(0).strip()
            if span and span not in matches:
                matches.append(span)
    if matches:
        return (True, " | ".join(matches))
    return (False, "")


def _pick_main_quote(text: str) -> str:
    """Pick the longest contiguous non-attribution block as the quote."""

    if not text:
        return ""
    blocks = [b.strip() for b in re.split(r"\n\s*\n", text) if b.strip()]
    if not blocks:
        return text.strip()
    # Drop blocks that are mostly attribution / URLs
    candidates: list[str] = []
    for b in blocks:
        if _WOL_URL.search(b) and len(b) < 80:
            continue
        if _PUB_CODE.search(b) and len(b) < 30:
            continue
        candidates.append(b)
    if not candidates:
        return blocks[0]
    return max(candidates, key=len)


def extract_quote(cleaned_text: str) -> ExtractedQuote:
    """Build an `ExtractedQuote` from cleaned OCR text."""

    cleaned_quote = _pick_main_quote(cleaned_text)
    has_attr, attr_text = _extract_attribution(cleaned_text)
    language = detect_language(cleaned_quote)
    return ExtractedQuote(
        raw_ocr_text=cleaned_text,
        cleaned_quote=cleaned_quote,
        language_detected=language,  # type: ignore[arg-type]
        has_attribution=has_attr,
        attribution_text=attr_text,
    )
