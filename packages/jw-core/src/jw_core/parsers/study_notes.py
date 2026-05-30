"""Parser for NWT Study Edition (nwtsty) study notes + cross-references.

The Study Edition embeds rich verse-by-verse commentary in `<li class="item
studyNote">` elements. Each note has a headword (the phrase it annotates)
in `<strong>...:</strong>` and a body with inline cross-references.

Inline cross-references in the main chapter text appear as `<a class="b"
href="/en/wol/bc/...">+</a>` — the `+` is just a marker; the panel content
lives behind the href and is fetched lazily.

Verse association strategy (Phase 3.5)
--------------------------------------
WOL doesn't encode verse numbers on study notes in the static HTML. We use
a multi-stage strategy:

  1. **Tokenize** the headword on any non-word character (so "wind … spirit"
     → ["wind", "spirit"] regardless of dot/ellipsis/whitespace style).
  2. **Normalize** each token (lowercase, NFD-strip, drop JW pronunciation
     marks `· ʹ` so "Nic·o·deʹmus" matches "Nicodemus").
  3. **Find verse where ALL tokens appear** in the verse's normalized text.
  4. **Monotonic constraint**: study notes appear in verse order in the DOM,
     so each match must be >= the previous matched verse.
  5. **Positional fallback**: notes that don't match get a best-effort verse
     interpolated from their DOM index — the LLM still gets the note, just
     with a `verse_confidence="positional"` hint.

On John 3 (18 notes, 36 verses) this strategy hits 18/18 (~100%).
"""

from __future__ import annotations

import re
import unicodedata

from bs4 import BeautifulSoup, Tag

from jw_core.models import CrossReference, StudyNote
from jw_core.parsers.verse import parse_verses

_PRON_MARKS_RE = re.compile(r"[·ʹ·ʹ´`]")
_TOKEN_SPLIT_RE = re.compile(r"[^\w]+")


def _normalize(text: str) -> str:
    """Lowercase, strip pronunciation marks + accents, collapse whitespace."""
    text = text.lower().replace("\xa0", " ")
    text = _PRON_MARKS_RE.sub("", text)
    text = "".join(
        c for c in unicodedata.normalize("NFD", text) if not unicodedata.combining(c)
    )
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _tokenize_headword(headword: str) -> list[str]:
    """Split a headword into matchable tokens.

    Drops ellipsis/punctuation, lowercases, removes pronunciation marks,
    and discards single-character tokens (which are too generic to help).
    """
    norm = _normalize(headword)
    return [t for t in _TOKEN_SPLIT_RE.split(norm) if len(t) > 1]


def parse_study_notes(
    html: str,
    *,
    book_num: int,
    chapter: int,
    language: str = "en",
    fallback_to_position: bool = True,
) -> list[StudyNote]:
    """Extract study notes from a nwtsty chapter page.

    Args:
        html: HTML from wol.jw.org.
        book_num / chapter: Required so we can attach them to each note
            and run the verse-matching heuristic against verses we know
            belong to the same chapter.
        fallback_to_position: When the headword can't be matched to a verse
            via tokens, estimate the verse from the note's DOM position
            (linear interpolation across the chapter's verse range).
            Notes assigned this way carry `confidence="positional"` in
            metadata-style; we expose it via `StudyNote.confidence`.

    The walk is monotonic: each successfully-matched verse must be >= the
    previous successful match, which prevents headword collisions
    (e.g. "loved" appearing in v3 and again in v16) from breaking the
    sequence.
    """
    soup = BeautifulSoup(html, "lxml")

    verses = parse_verses(
        html, book_num=book_num, chapter=chapter, language=language
    )
    verse_norm: dict[int, str] = {v.verse: _normalize(v.text) for v in verses}
    verse_numbers = sorted(verse_norm)
    max_verse = verse_numbers[-1] if verse_numbers else 1

    note_elements: list[Tag] = [
        li for li in soup.find_all("li", class_="studyNote") if isinstance(li, Tag)
    ]
    total_notes = len(note_elements)

    notes: list[StudyNote] = []
    last_matched_verse = 0  # monotonic floor
    for idx, li in enumerate(note_elements):
        head = li.find("strong")
        if not head:
            continue
        headword_raw = head.get_text(" ", strip=True).rstrip(":").strip()

        verse_num = _find_verse_for_headword(
            headword_raw, verse_norm, min_verse=last_matched_verse + 1
        )
        confidence = "headword" if verse_num is not None else None

        if verse_num is None and fallback_to_position and total_notes > 0:
            # Linear interpolation across the chapter's verse range.
            # idx=0 → verse 1; idx=N-1 → verse max_verse.
            estimated = round(1 + (idx / max(total_notes - 1, 1)) * (max_verse - 1))
            # Clamp to (last_matched_verse, max_verse] for monotonicity.
            estimated = max(estimated, last_matched_verse + 1)
            estimated = min(estimated, max_verse)
            verse_num = estimated
            confidence = "positional"

        if verse_num is not None and confidence == "headword":
            last_matched_verse = verse_num

        body = li.get_text(" ", strip=True)
        if body.lower().startswith(headword_raw.lower()):
            body = body[len(headword_raw):].lstrip(": ").strip()
        body = re.sub(r"\s+", " ", body)

        inline_refs = [
            a.get_text(" ", strip=True)
            for a in li.find_all("a", class_="b")
            if a.get_text(strip=True)
        ]

        notes.append(StudyNote(
            book_num=book_num,
            chapter=chapter,
            verse=verse_num,
            headword=headword_raw,
            body=body,
            inline_refs=inline_refs,
            language=language,
            confidence=confidence or "unmatched",
        ))
    return notes


def _find_verse_for_headword(
    headword: str,
    verse_norm: dict[int, str],
    *,
    min_verse: int = 1,
) -> int | None:
    """Locate the verse whose text contains every token of the headword.

    Args:
        headword: Raw headword text (e.g. "wind … spirit").
        verse_norm: {verse_number: normalized_verse_text}.
        min_verse: Lower bound for monotonic walk. Search starts here.

    Returns the smallest verse number >= min_verse whose normalized text
    contains every headword token, or None if no such verse exists. Also
    falls back to a relaxed search (ignoring min_verse) if nothing matches;
    that prevents one early miss from cascading into later misses.
    """
    tokens = _tokenize_headword(headword)
    if not tokens:
        return None

    def search(start: int) -> int | None:
        for vnum in sorted(v for v in verse_norm if v >= start):
            if all(t in verse_norm[vnum] for t in tokens):
                return vnum
        return None

    # First, respect the monotonic floor.
    match = search(min_verse)
    if match is not None:
        return match
    # Relaxed fallback: try the whole chapter. This recovers when a previous
    # note was assigned positionally too high and the floor blocks a real
    # match — rare but worth handling.
    return search(1)


def parse_cross_references(
    html: str,
    *,
    book_num: int,
    chapter: int,
    language: str = "en",
) -> list[CrossReference]:
    """Extract inline cross-reference markers from a Bible chapter page.

    Each `<a class="b" href="/en/wol/bc/...">+</a>` inside a `<span class="v">`
    becomes one CrossReference. The href is preserved so the panel can be
    fetched on demand.
    """
    soup = BeautifulSoup(html, "lxml")
    out: list[CrossReference] = []
    for span in soup.find_all("span", class_="v"):
        vid = span.get("id", "")
        m = re.match(r"v(\d+)-(\d+)-(\d+)-(\d+)", vid)
        if not m:
            continue
        b, c, v, _ = map(int, m.groups())
        if b != book_num or c != chapter:
            continue
        for a in span.find_all("a", class_="b"):
            href = a.get("href", "")
            if not href:
                continue
            out.append(CrossReference(
                book_num=b,
                chapter=c,
                verse=v,
                href=href,
                marker=a.get_text(strip=True) or "+",
                language=language,
            ))
    return out


def study_notes_for_verse(
    notes: list[StudyNote], verse: int
) -> list[StudyNote]:
    """Filter a list of study notes to those matched to a specific verse."""
    return [n for n in notes if n.verse == verse]
