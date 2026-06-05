"""Parser de URLs WOL bíblicas → BibleRef.

Port a Python del BibleRef.fromWolUrl() del paquete jw-core-js (F56.5).
Reglas:
- URLs `/wol/b/<resource>/<lp_tag>/<pub>/<book_num>/<chapter>` son bíblicas.
- Anchor opcional `#study=...&v=<book>:<chap>:<verse>` o
  `&v=<book>:<chap>:<verse_start>-<book>:<chap>:<verse_end>`.
- Otros patrones (`/wol/d/...`, `/wol/dt/...`, etc.) devuelven None.
"""

from __future__ import annotations

import re

from jw_core.data.books import BOOKS
from jw_core.models import BibleRef

_BIBLE_URL_RE = re.compile(
    r"^/(?P<lang>[a-z]{2,3})/wol/b/(?P<resource>r\d+)/(?P<lp_tag>lp-[a-z]+)/"
    r"(?P<pub>[a-z]+)/(?P<book>\d{1,2})/(?P<chapter>\d{1,3})(?:[#?].*)?$"
)
_VERSE_ANCHOR_RE = re.compile(
    r"[?&#]v=(?P<book>\d{1,2}):(?P<chap>\d{1,3}):(?P<start>\d{1,3})"
    r"(?:-\d{1,2}:\d{1,3}:(?P<end>\d{1,3}))?"
)
_LANG_TO_LETTER: dict[str, str] = {"en": "E", "es": "S", "pt": "T"}


def parse_wol_bible_url(href: str) -> BibleRef | None:
    """Parsea una URL WOL bíblica a BibleRef. Devuelve None si no aplica."""
    if not href or not href.startswith("/"):
        return None
    m = _BIBLE_URL_RE.match(href)
    if not m:
        return None
    book_num = int(m.group("book"))
    chapter = int(m.group("chapter"))
    if not (1 <= book_num <= 66):
        return None

    verse_start: int | None = None
    verse_end: int | None = None
    anchor_match = _VERSE_ANCHOR_RE.search(href)
    if anchor_match and int(anchor_match.group("book")) == book_num:
        verse_start = int(anchor_match.group("start"))
        if anchor_match.group("end"):
            verse_end = int(anchor_match.group("end"))
        else:
            verse_end = verse_start

    detected_letter = _LANG_TO_LETTER.get(m.group("lang"), "E")
    book_meta = BOOKS[book_num - 1]
    return BibleRef(
        book_num=book_num,
        book_canonical=book_meta["canonical"],
        chapter=chapter,
        verse_start=verse_start,
        verse_end=verse_end,
        detected_language=detected_letter,
        raw_match=href,
    )
