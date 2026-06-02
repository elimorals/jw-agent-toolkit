"""Stage 1 — cheap heuristics, always-on, no network.

Two checks:
  - cites_jw_publication(answer): does the answer mention any JW publication
    code (w/g/jt/bh/sjj/...) OR a wol.jw.org URL? Conservative regex set —
    false positives accepted only if the pub code is preceded by a word boundary.
  - has_minimum_substance(question, answer): does the answer have teaching
    content, not just "Yes" / a literal echo of the question / too short?

The lists of "generic answers" are language-agnostic enough that we cover
es/en/pt with a small union set.
"""

from __future__ import annotations

import re

_JW_PUB_CODES = re.compile(
    r"\b("
    r"w\d{2,}|"
    r"ws\d{2,}|"
    r"wp\d{2,}|"
    r"g\d{2,}|"
    r"jt|"
    r"bh|"
    r"sjj|sjjm|"
    r"jy|"
    r"rs|"
    r"it|"
    r"km\d{2,}|"
    r"yb\d{2,}|"
    r"sg|"
    r"cl|"
    r"lvs|"
    r"lff|"
    r"lr|"
    r"sjm"
    r")\b",
    re.IGNORECASE,
)

_WOL_URL = re.compile(r"https?://(?:www\.)?wol\.jw\.org/", re.IGNORECASE)


def cites_jw_publication(answer: str) -> bool:
    """True if `answer` contains a wol.jw.org URL or a known JW pub code."""

    if not answer:
        return False
    return bool(_WOL_URL.search(answer) or _JW_PUB_CODES.search(answer))


_GENERIC_ANSWERS: frozenset[str] = frozenset(
    {
        "sí.",
        "sí",
        "no.",
        "no",
        "depende.",
        "depende",
        "tal vez",
        "puede ser",
        "no sé.",
        "no sé",
        "yes.",
        "yes",
        "maybe.",
        "maybe",
        "it depends.",
        "it depends",
        "i don't know.",
        "i don't know",
        "sim.",
        "sim",
        "não.",
        "não",
        "talvez.",
        "talvez",
        "não sei.",
        "não sei",
    }
)


def has_minimum_substance(question: str, answer: str) -> bool:
    """True if the answer is long enough, not generic, not a question echo."""

    if not answer:
        return False
    a = answer.strip()
    if len(a) < 40:
        return False
    if a.lower() in _GENERIC_ANSWERS:
        return False
    if not question:
        return True
    q = question.strip().lower()
    a_lower = a.lower()
    if q and a_lower.startswith(q) and len(a_lower) < len(q) + 30:
        return False
    return True
