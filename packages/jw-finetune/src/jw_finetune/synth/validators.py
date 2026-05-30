"""Validators for synthesized Q&A pairs.

Bible-reference detection uses `jw_core.parsers.reference.parse_all_references`
which has language-aware book name canonicalization and handles:
  * Abbreviations (Mat, Sl, 1Co, etc.)
  * Cross-chapter ranges (Mat 24:14–25:46)
  * Comma-separated verse lists (Mat 24:14, 21, 30)
  * Multiple languages (es, en, pt, fr, de, ...) registered in `jw_core.languages`

This is a substantial upgrade over the previous hand-rolled regex that
only matched the obvious "Book chapter:verse" form.
"""

from __future__ import annotations

import logging

try:
    import langdetect  # type: ignore[import-untyped]

    _HAS_LANGDETECT = True
except ImportError:
    langdetect = None  # type: ignore[assignment]
    _HAS_LANGDETECT = False

logger = logging.getLogger(__name__)


def is_valid_bible_ref(text: str) -> bool:
    """True if `text` contains at least one well-formed bible reference."""
    from jw_core.parsers.reference import parse_all_references

    try:
        refs = parse_all_references(text)
    except Exception as e:  # noqa: BLE001
        logger.debug("parse_all_references error: %s", e)
        return False
    return len(refs) > 0


def count_bible_refs(text: str) -> int:
    """Count distinct bible references in `text` via jw_core parser."""
    from jw_core.parsers.reference import parse_all_references

    try:
        refs = parse_all_references(text)
    except Exception as e:  # noqa: BLE001
        logger.debug("parse_all_references error: %s", e)
        return 0
    return len(refs)


def length_ok(
    question: str,
    answer: str,
    *,
    q_min: int = 5,
    q_max: int = 400,
    a_min: int = 30,
    a_max: int = 2000,
) -> bool:
    """Reject empty/too-short/too-long Q&A pairs."""
    q = (question or "").strip()
    a = (answer or "").strip()
    return q_min <= len(q) <= q_max and a_min <= len(a) <= a_max


def lang_matches(text: str, expected: str) -> bool:
    """Returns True if detected language matches `expected` (ISO 639-1)."""
    if not _HAS_LANGDETECT:
        return True
    try:
        detected = langdetect.detect(text)
        return detected[:2].lower() == expected[:2].lower()
    except Exception:
        return True
