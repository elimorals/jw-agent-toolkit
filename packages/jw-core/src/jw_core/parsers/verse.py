"""Parser for individual verses from a wol.jw.org Bible chapter (nwtsty).

WOL marks each verse with `<span class="v" id="v{book}-{ch}-{verse}-{N}">`.
A single verse may have multiple instances (the same id pattern repeats
for sub-spans like footnote markers or pronunciation breaks).

This parser concatenates all spans for the same verse, strips noise
(pronunciation marks like `·` `ʹ`, inline `+` cross-ref markers, leading
verse number), and returns a list of clean `Verse` objects in order.
"""

from __future__ import annotations

import re

from bs4 import BeautifulSoup

from jw_core.models import Verse

_VERSE_ID_RE = re.compile(r"v(\d+)-(\d+)-(\d+)-(\d+)")
_LEADING_NUM_RE = re.compile(r"^\s*\d+\s*")
_INLINE_MARKER_RE = re.compile(r"\s*\+\s*")
_PRON_MARKS_RE = re.compile(r"[·ʹ·ʹ]")


def parse_verses(
    html: str,
    *,
    book_num: int | None = None,
    chapter: int | None = None,
    language: str = "en",
    strip_pronunciation: bool = True,
) -> list[Verse]:
    """Extract all verses from a nwtsty chapter HTML.

    Args:
        html: Raw HTML from wol.jw.org chapter page.
        book_num / chapter: Optional filters. If provided, only verses whose
            id matches book_num and chapter are returned.
        language: ISO code stored on each Verse for later URL building.
        strip_pronunciation: Remove JW pronunciation marks (· ʹ). Default True.
    """
    soup = BeautifulSoup(html, "lxml")
    by_verse: dict[tuple[int, int, int], list[str]] = {}

    for span in soup.find_all("span", class_="v"):
        vid = span.get("id", "")
        m = _VERSE_ID_RE.match(vid)
        if not m:
            continue
        b, c, v, _instance = map(int, m.groups())
        if book_num is not None and b != book_num:
            continue
        if chapter is not None and c != chapter:
            continue
        # Strip inline footnote markers (`*`) and the `+` cross-ref symbols
        # before extracting text. We replace the elements rather than mutate
        # the parsed tree so the soup remains intact for other parsers.
        text = span.get_text(" ", strip=True)
        text = _LEADING_NUM_RE.sub("", text)
        text = _INLINE_MARKER_RE.sub(" ", text)
        text = text.replace("*", "").replace("\xa0", " ")
        if strip_pronunciation:
            text = _PRON_MARKS_RE.sub("", text)
        # Collapse internal whitespace.
        text = re.sub(r"\s+", " ", text).strip()
        if text:
            by_verse.setdefault((b, c, v), []).append(text)

    return [
        Verse(
            book_num=b,
            chapter=c,
            verse=v,
            text=" ".join(parts).strip(),
            language=language,
        )
        for (b, c, v), parts in sorted(by_verse.items())
    ]


def get_verse(html: str, book_num: int, chapter: int, verse: int, *, language: str = "en") -> Verse | None:
    """Convenience: parse and return one specific verse, or None."""
    for v in parse_verses(html, book_num=book_num, chapter=chapter, language=language):
        if v.verse == verse:
            return v
    return None
