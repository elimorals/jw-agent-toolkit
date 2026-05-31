"""Cross-language helpers that preserve Bible references.

VISION.md: "Traducción automática entre idiomas preservando referencias
bíblicas exactas".

The challenge: if a user paste a Spanish text containing "Juan 3:16" and
asks an LLM to translate to English, the LLM is likely to render it as
"John 3:16" but might also accidentally rewrite the verse text. We
provide:

  - `mask_references(text)` → text with refs replaced by tokens like
    `<<REF:0>>`, plus a side-list of canonical refs.
  - `restore_references(text, refs, target_lang)` → re-injects the refs
    rendered in the target language.

Use this as a pre/post hook around any LLM translation call.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from jw_core.data.books import BOOKS
from jw_core.languages import get_language
from jw_core.parsers.reference import parse_all_references


@dataclass
class MaskedText:
    text: str  # with `<<REF:i>>` tokens in place of references
    references: list[dict[str, object]] = field(default_factory=list)


_REF_TOKEN_RE = re.compile(r"<<REF:(\d+)>>")


def mask_references(text: str) -> MaskedText:
    """Mask each detected Bible reference with a token; preserve metadata."""
    refs = parse_all_references(text)
    if not refs:
        return MaskedText(text=text, references=[])

    # Replace by START position descending so indices stay valid.
    ordered = sorted(
        ((m, ref) for m, ref in _iter_matches(text, refs)),
        key=lambda x: x[0].start(),
        reverse=True,
    )
    masked = text
    references_payload: list[dict[str, object]] = []
    # We'll build a stable ordered list — assign indices in the order they
    # appear in the ORIGINAL text (low → high).
    in_order = sorted(((m.start(), m, ref) for m, ref in _iter_matches(text, refs)), key=lambda x: x[0])
    for idx, (_, _, ref) in enumerate(in_order):
        references_payload.append(
            {
                "index": idx,
                "book_num": ref.book_num,
                "chapter": ref.chapter,
                "verse_start": ref.verse_start,
                "verse_end": ref.verse_end,
                "raw_match": ref.raw_match,
                "detected_language": ref.detected_language,
            }
        )
    for match, ref in ordered:
        idx = next(i for i, p in enumerate(references_payload) if p["raw_match"] == ref.raw_match)
        masked = masked[: match.start()] + f"<<REF:{idx}>>" + masked[match.end() :]
    return MaskedText(text=masked, references=references_payload)


def _iter_matches(text: str, refs):  # type: ignore[no-untyped-def]
    """Iterate (start, end, BibleRef) tuples, locating each raw_match case-insensitively."""
    lower = text.lower()
    cursor = 0
    used = set()
    for ref in refs:
        needle = ref.raw_match.lower()
        start = lower.find(needle, cursor)
        if start == -1 or start in used:
            continue
        end = start + len(needle)
        used.add(start)

        class _M:
            def __init__(self, s: int, e: int) -> None:
                self._s, self._e = s, e

            def start(self) -> int:
                return self._s

            def end(self) -> int:
                return self._e

        yield _M(start, end), ref
        cursor = end


def restore_references(
    masked_text: str,
    references: list[dict[str, object]],
    *,
    target_language: str = "en",
) -> str:
    """Re-inject canonical references rendered in the target language."""
    lang = get_language(target_language)

    def replace(match: re.Match[str]) -> str:
        idx = int(match.group(1))
        if idx >= len(references):
            return match.group(0)
        ref = references[idx]
        return render_reference(
            book_num=int(ref["book_num"]),  # type: ignore[arg-type]
            chapter=int(ref["chapter"]),  # type: ignore[arg-type]
            verse_start=ref["verse_start"],  # type: ignore[arg-type]
            verse_end=ref["verse_end"],  # type: ignore[arg-type]
            language=lang.iso,
        )

    return _REF_TOKEN_RE.sub(replace, masked_text)


def render_reference(
    *,
    book_num: int,
    chapter: int,
    verse_start: int | None = None,
    verse_end: int | None = None,
    language: str = "en",
) -> str:
    """Render the canonical short name in `language` (uses BOOKS table)."""
    book_entry = BOOKS[book_num - 1] if 0 < book_num <= len(BOOKS) else None
    if not book_entry:
        return f"Book{book_num} {chapter}"
    names = book_entry["names"]
    candidates = names.get(language) or names.get("en") or next(iter(names.values()))
    name = candidates[0] if candidates else book_entry["canonical"]
    out = f"{name} {chapter}"
    if verse_start:
        out += f":{verse_start}"
        if verse_end and verse_end != verse_start:
            out += f"-{verse_end}"
    return out
