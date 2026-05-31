"""Multi-language Bible reference parser.

Resolves natural-language references like "Juan 3:16", "1 Corintios 13:4-7",
"Heb 13", "John 3:16-18" into structured BibleRef objects with canonical book
numbers and wol.jw.org URLs.

Languages supported (Phase 1): English (en), Spanish (es), Portuguese (pt).
Extend by appending entries to jw_core.data.books.BOOKS.

The parser:
  1. Normalizes input (lowercase + accent-strip) so "Génesis" matches "genesis".
  2. Builds a single master regex from BOOKS with all names + abbreviations.
  3. Sorts alternatives longest-first so "1 Corintios" wins over "Corintios".
  4. Looks up matched book in an index keyed by space-stripped normalized form.
"""

from __future__ import annotations

import re
import unicodedata
from functools import lru_cache

from pydantic import ValidationError as _ValidationError

from jw_core.data.books import BOOKS
from jw_core.models import BibleRef

__all__ = [
    "BibleRef",
    "ReferenceParser",
    "parse_all_references",
    "parse_reference",
]


def _norm(s: str) -> str:
    """Lowercase + remove combining accents. Preserves spaces, digits, punct."""
    return "".join(c for c in unicodedata.normalize("NFD", s.lower()) if not unicodedata.combining(c))


def _norm_key(s: str) -> str:
    """Normalize and strip whitespace, dots, hyphens.

    Used to build the lookup index: 'corintios' and '1 corintios' produce
    distinct keys ('corintios' vs '1corintios').
    """
    return re.sub(r"[\s.\-]+", "", _norm(s))


class ReferenceParser:
    """Multi-language Bible reference parser.

    A single instance is enough for the whole process (regex is compiled once).
    Use the module-level `parse_reference` / `parse_all_references` helpers in
    most cases.
    """

    def __init__(self) -> None:
        # name_key (normalized, no spaces) -> (book_num, lang, canonical)
        self._index: dict[str, tuple[int, str, str]] = {}
        # All recognized display forms (normalized, spaces preserved)
        display_forms: set[str] = set()

        for book in BOOKS:
            for lang, names in book["names"].items():
                for name in names:
                    display = _norm(name).strip()
                    key = _norm_key(name)
                    if not key:
                        continue
                    # Two different language entries can produce the same key
                    # (e.g. "Jonás" → "jonas" and Portuguese "Jonas" → "jonas").
                    # First entry wins for language attribution; book_num and
                    # canonical are identical across collisions, so it's safe.
                    self._index.setdefault(key, (book["num"], lang, book["canonical"]))
                    display_forms.add(display)

        self._regex = self._compile_master_regex(display_forms)

    @staticmethod
    def _compile_master_regex(display_forms: set[str]) -> re.Pattern[str]:
        # Sort by length DESC so longer alternatives win regex alternation:
        # "1 corintios" must be tried before "corintios" alone.
        ordered = sorted(display_forms, key=len, reverse=True)

        # In each alternative, replace internal spaces with \s+ to tolerate
        # variable whitespace ("1  Corintios", "1 Corintios").
        alternatives = []
        for d in ordered:
            parts = d.split(" ")
            alternatives.append(r"\s+".join(re.escape(p) for p in parts))

        book_alt = "|".join(alternatives)

        # Pattern: book <chapter>[(:|.) <verse>[(-|–|—) <verse_end>]]
        # \b before the book to require a word boundary (avoid mid-word hits).
        # Chapter is required; verse and verse_end are optional.
        pattern = (
            rf"\b(?P<book>{book_alt})\s*"
            rf"(?P<chapter>\d+)"
            rf"(?:\s*[:.]\s*(?P<verse_start>\d+)"
            rf"(?:\s*[-–—]\s*(?P<verse_end>\d+))?)?"
        )
        return re.compile(pattern, re.IGNORECASE)

    def parse(self, text: str) -> list[BibleRef]:
        """Find all Bible references in `text`."""
        if not text:
            return []
        normalized = _norm(text)
        refs: list[BibleRef] = []
        for m in self._regex.finditer(normalized):
            book_match = m.group("book")
            key = _norm_key(book_match)
            entry = self._index.get(key)
            if entry is None:
                # Shouldn't happen given the regex was built from index keys,
                # but be defensive against future regex changes.
                continue
            book_num, lang, canonical = entry
            verse_start_raw = m.group("verse_start")
            verse_end_raw = m.group("verse_end")
            try:
                ref = BibleRef(
                    book_num=book_num,
                    book_canonical=canonical,
                    chapter=int(m.group("chapter")),
                    verse_start=int(verse_start_raw) if verse_start_raw else None,
                    verse_end=int(verse_end_raw) if verse_end_raw else None,
                    detected_language=lang,
                    raw_match=normalized[m.start() : m.end()].strip(),
                )
            except _ValidationError:
                # Regex matched but the numbers fall outside the valid
                # BibleRef bounds (e.g. chapter=0 from a fuzzed input).
                # Skip silently — the contract is "return refs or []".
                continue
            refs.append(ref)
        return refs

    def parse_one(self, text: str) -> BibleRef | None:
        """Return the first reference found, or None."""
        refs = self.parse(text)
        return refs[0] if refs else None


@lru_cache(maxsize=1)
def _singleton() -> ReferenceParser:
    return ReferenceParser()


def parse_reference(text: str) -> BibleRef | None:
    """Parse the first Bible reference in `text`. Returns None if no match."""
    return _singleton().parse_one(text)


def parse_all_references(text: str) -> list[BibleRef]:
    """Parse every Bible reference in `text`."""
    return _singleton().parse(text)
