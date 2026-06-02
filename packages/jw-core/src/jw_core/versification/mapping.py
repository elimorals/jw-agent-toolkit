"""to_canonical: map a (book, chapter, verse_start, verse_end) coordinate
between numbering traditions.

Idempotent: if from_tradition == to_tradition, returns the input wrapped in
a MappingResult with is_discrepant=False.

Lossless on round-trip for catalog entries: applying the mapping forward
and then backward yields the original coordinate.

The lookup is conservative — we match on (book_num, chapter, verse_start)
in the `from_tradition` coordinate of each catalog row. Multi-verse ranges
(verse_end set) match only when the request's start matches the catalog
row's start; the rest of the range is shifted by the catalog's chapter and
verse offset.
"""

from __future__ import annotations

from jw_core.versification.models import (
    MappingResult,
    Tradition,
    VerseCoord,
    VersificationMapping,
)
from jw_core.versification.registry import load_catalog

_TRADITIONS: tuple[Tradition, ...] = ("nwt", "masoretic", "lxx", "vulgate")


def _find_entry(
    book_num: int,
    coord: VerseCoord,
    *,
    from_tradition: Tradition,
    to_tradition: Tradition,
) -> VersificationMapping | None:
    for entry in load_catalog():
        if entry.book_num != book_num:
            continue
        src = entry.coord_for(from_tradition)
        dst = entry.coord_for(to_tradition)
        if src is None or dst is None:
            continue
        if src.chapter != coord.chapter:
            continue
        if src.verse_start != coord.verse_start:
            continue
        return entry
    return None


def to_canonical(
    *,
    book: str,
    book_num: int,
    chapter: int,
    verse_start: int,
    verse_end: int | None = None,
    from_tradition: Tradition = "nwt",
    to_tradition: Tradition,
) -> MappingResult:
    """Map a (book, chapter, verse_start, verse_end) coordinate.

    Raises ValueError if either tradition is unknown.
    """

    if from_tradition not in _TRADITIONS:
        raise ValueError(f"Unknown from_tradition: {from_tradition!r}")
    if to_tradition not in _TRADITIONS:
        raise ValueError(f"Unknown to_tradition: {to_tradition!r}")

    coord = VerseCoord(
        chapter=chapter, verse_start=verse_start, verse_end=verse_end
    )

    if from_tradition == to_tradition:
        return MappingResult(
            ref_book=book,
            ref_book_num=book_num,
            coord=coord,
            from_tradition=from_tradition,
            to_tradition=to_tradition,
            is_discrepant=False,
        )

    entry = _find_entry(
        book_num,
        coord,
        from_tradition=from_tradition,
        to_tradition=to_tradition,
    )
    if entry is None:
        return MappingResult(
            ref_book=book,
            ref_book_num=book_num,
            coord=coord,
            from_tradition=from_tradition,
            to_tradition=to_tradition,
            is_discrepant=False,
        )

    src = entry.coord_for(from_tradition)
    dst = entry.coord_for(to_tradition)
    assert src is not None and dst is not None

    chapter_delta = dst.chapter - src.chapter
    verse_delta = dst.verse_start - src.verse_start

    new_chapter = max(0, coord.chapter + chapter_delta)
    new_start = max(0, coord.verse_start + verse_delta)
    new_end: int | None
    if coord.verse_end is not None:
        new_end = max(0, coord.verse_end + verse_delta)
    else:
        new_end = None

    rationale = entry.explanation.get("en")
    return MappingResult(
        ref_book=entry.book,
        ref_book_num=entry.book_num,
        coord=VerseCoord(
            chapter=new_chapter, verse_start=new_start, verse_end=new_end
        ),
        from_tradition=from_tradition,
        to_tradition=to_tradition,
        is_discrepant=True,
        rationale=rationale,
    )
