"""Human-readable explainer for a (book, chapter, verse) discrepancy.

Returns None when the mapping is trivial (identical reference). Otherwise
returns the explanation string in the requested language (defaults to en).
"""

from __future__ import annotations

from typing import Literal

from jw_core.versification.mapping import to_canonical
from jw_core.versification.models import Tradition

Language = Literal["en", "es", "pt"]


def explain(
    *,
    book: str,
    book_num: int,
    chapter: int,
    verse_start: int,
    verse_end: int | None = None,
    from_tradition: Tradition,
    to_tradition: Tradition,
    language: Language = "en",
) -> str | None:
    """Return a human-readable sentence describing the discrepancy."""

    if from_tradition == to_tradition:
        return None

    result = to_canonical(
        book=book,
        book_num=book_num,
        chapter=chapter,
        verse_start=verse_start,
        verse_end=verse_end,
        from_tradition=from_tradition,
        to_tradition=to_tradition,
    )
    if not result.is_discrepant:
        return None

    from jw_core.versification.registry import load_catalog

    for entry in load_catalog():
        if entry.book_num != book_num:
            continue
        src = entry.coord_for(from_tradition)
        if src is None:
            continue
        if src.chapter == chapter and src.verse_start == verse_start:
            text = entry.explanation.get(language)
            if text and text.strip():
                return text
            return entry.explanation.get("en")
    return None
