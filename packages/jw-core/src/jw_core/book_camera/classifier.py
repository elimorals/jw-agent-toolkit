"""Content classifier for book-camera OCR output (Fase 71).

Detects the kind of content visible in the image and produces a typed
`DetectedContent`. Conservative: prefers `plain_text` / `unknown` over
mis-classification.
"""

from __future__ import annotations

import re

from jw_core.book_camera.models import (
    BibleVerseDetected,
    DetectedContent,
    PlainTextDetected,
    StudyQuestionDetected,
    UnknownTextDetected,
    WatchtowerParagraphDetected,
)
from jw_core.parsers.reference import parse_all_references

_PUB_CODE = re.compile(
    r"\b("
    r"w\d{2,}|ws\d{2,}|wp\d{2,}|g\d{2,}|jt|bh|jy|rs|it|km\d{2,}|"
    r"yb\d{2,}|cl|lff"
    r")(\.\d{1,2})?\b",
    re.IGNORECASE,
)
_PARAGRAPH_NUM = re.compile(
    r"p[áa]rr(?:afo)?\.?\s*(\d{1,3})", re.IGNORECASE
)
_QUESTION_MARKS = re.compile(r"[¿?]")
_STUDY_QUESTION_HINTS = (
    "párrafo",
    "paragraph",
    "parágrafo",
    "preguntas",
    "questions",
    "answer the following",
)


def _bible_to_wol(book_num: int, chapter: int, verse: int | None) -> str:
    """Best-effort WOL URL builder (English defaults).

    The real builder is on BibleRef.wol_url; we replicate enough to
    decouple classifier tests from network/registry lookups.
    """
    base = "https://wol.jw.org/en/wol/b/r1/lp-e/nwt"
    if verse is not None:
        return f"{base}/{book_num}/{chapter}#study=discover&v={book_num}:{chapter}:{verse}"
    return f"{base}/{book_num}/{chapter}"


def _looks_like_question(text: str) -> bool:
    if not text:
        return False
    stripped = text.strip()
    if _QUESTION_MARKS.search(stripped):
        return True
    lowered = stripped.lower()
    if any(h in lowered for h in _STUDY_QUESTION_HINTS):
        # Don't classify mere mention of "paragraph"; require ? or topic.
        return _QUESTION_MARKS.search(stripped) is not None
    return False


def classify_content(ocr_text: str) -> DetectedContent:
    """Classify OCR text into one of the `DetectedContent` variants.

    Order of detection:
      1. Bible reference (first one wins)
      2. Watchtower paragraph (pub code + optional paragraph number)
      3. Study question (¿ / ? plus heuristic hints)
      4. Plain text (substantial alphanumeric content)
      5. Unknown (empty / noise)
    """

    if not ocr_text or not ocr_text.strip():
        return UnknownTextDetected(text="")

    text = ocr_text.strip()

    # 1) Bible reference
    refs = parse_all_references(text)
    if refs:
        ref = refs[0]
        return BibleVerseDetected(
            book_num=ref.book_num,
            chapter=ref.chapter,
            verse_start=ref.verse_start,
            verse_end=ref.verse_end,
            detected_language=ref.detected_language,
            wol_url=_bible_to_wol(
                ref.book_num, ref.chapter, ref.verse_start
            ),
        )

    # 2) Watchtower paragraph (pub code in body)
    pub_match = _PUB_CODE.search(text)
    if pub_match:
        para_id: int | None = None
        para_match = _PARAGRAPH_NUM.search(text)
        if para_match:
            try:
                para_id = int(para_match.group(1))
            except ValueError:
                para_id = None
        return WatchtowerParagraphDetected(
            pub_code=pub_match.group(0),
            paragraph_id=para_id,
            text=text,
        )

    # 3) Study question
    if _looks_like_question(text):
        return StudyQuestionDetected(text=text, suggested_topics=[])

    # 4) Plain text vs unknown
    if any(c.isalnum() for c in text) and len(text) >= 4:
        return PlainTextDetected(text=text)
    return UnknownTextDetected(text=text)
