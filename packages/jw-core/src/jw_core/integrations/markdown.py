"""Markdown ↔ JW Library utilities (Phase 20).

Ports the high-leverage helpers from `msakowski/obsidian-library-linker`
(MIT) so any markdown-aware agent or editor can:

  - **linkify**: turn plain text "Juan 3:16" into `[Juan 3:16](jwlibrary:///finder?bible=…)`.
  - **convert** legacy `jwpub://b/...` and `jwpub://p/...` references to
    modern `jwlibrary://` deep links.
  - **parse** a `jwlibrary:///finder?bible=…` URL back into a `BibleRef`
    (inverse of `build_bible_url`).
  - **render** a `BibleRef` plus optional verse text into multiple
    markdown templates (plain link, blockquote, Obsidian callout, …).

Everything is a pure function over strings — no I/O, no network. The
network-facing variant (fetch verse → render with quote) lives in the
MCP server, not here.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Literal

from jw_core.data.book_locales import JW_CODE_TO_ISO, load_book_locale
from jw_core.integrations.jw_library import (
    build_bible_url,
    build_publication_url,
)
from jw_core.languages import get_book_language, get_language
from jw_core.models import BibleRef
from jw_core.parsers.reference import _singleton, parse_all_references  # noqa: F401

__all__ = [
    "ConversionStats",
    "LinkifyResult",
    "NameLength",
    "QuoteTemplate",
    "convert_jw_links_in_text",
    "convert_jwpub_bible_url",
    "convert_jwpub_publication_url",
    "linkify_markdown",
    "parse_jwlibrary_url",
    "render_markdown_link",
    "render_verse_block",
]


# Public type aliases for the MCP layer.
NameLength = Literal["long", "medium", "short"]
QuoteTemplate = Literal["plain", "link", "blockquote", "callout", "callout-collapsed"]


# ── Parse: jwlibrary:// → BibleRef ────────────────────────────────────


_JWLIB_BIBLE_RE = re.compile(
    r"jwlibrary:///finder\?bible=(\d{8})(?:-(\d{8}))?(?:&[^)\s]*)?",
)
_JWPUB_BIBLE_RE = re.compile(
    r"jwpub://b/(\d+):(\d+):(\d+)-(\d+):(\d+):(\d+)",
)
_JWPUB_PUB_RE = re.compile(
    r"jwpub://p/(?P<locale>[a-zA-Z0-9-]+):(?P<docid>\d+)(?:/(?P<par>\d+))?",
)


def _split_bbcccvvv(token: str) -> tuple[int, int, int]:
    if len(token) != 8:
        raise ValueError(f"Invalid jwlibrary bible code: {token!r}")
    return int(token[:2]), int(token[2:5]), int(token[5:8])


def parse_jwlibrary_url(url: str, *, language: str | None = None) -> BibleRef | None:
    """Reverse of `build_bible_url` — extract a `BibleRef` from a deep link.

    Returns None when the URL does not match the `?bible=` shape (e.g.
    `?docid=` publication URLs, or unrelated jwlibrary URLs).
    """
    if not url:
        return None
    m = _JWLIB_BIBLE_RE.search(url)
    if not m:
        return None
    start_token = m.group(1)
    end_token = m.group(2)
    try:
        sb, sc, sv = _split_bbcccvvv(start_token)
    except ValueError:
        return None
    book_num = sb
    chapter = sc
    verse_start = sv
    verse_end: int | None = None
    if end_token:
        try:
            eb, ec, ev = _split_bbcccvvv(end_token)
        except ValueError:
            return None
        if eb == sb and ec == sc:
            verse_end = ev if ev != sv else None
        else:
            # Multi-chapter: we don't have a place to store end_chapter on
            # BibleRef, so we surface only the start side. Callers needing
            # the full range should re-parse from text.
            verse_end = ev

    lang_iso = language
    if lang_iso is None:
        wt_match = re.search(r"wtlocale=([A-Za-z-]+)", url)
        if wt_match:
            jw_code = wt_match.group(1).upper()
            lang_iso = JW_CODE_TO_ISO.get(jw_code, jw_code).lower()
    return BibleRef(
        book_num=book_num,
        book_canonical=_canonical_name(book_num),
        chapter=chapter,
        verse_start=verse_start,
        verse_end=verse_end,
        detected_language=lang_iso or "en",
        raw_match=url,
    )


def _canonical_name(book_num: int) -> str:
    from jw_core.data.books import BOOKS

    for b in BOOKS:
        if b["num"] == book_num:
            return b["canonical"]
    return ""


# ── Convert: jwpub:// → jwlibrary:// ──────────────────────────────────


def convert_jwpub_bible_url(url: str, *, wtlocale: str | None = None) -> str | None:
    """Convert a `jwpub://b/BB:CCC:VVV-BB:CCC:VVV` URL to `jwlibrary://`.

    The `jwpub://b/` scheme is the legacy desktop-app form (Watchtower
    Library, Logos, etc.). Some user notes still contain them. We unpack
    book/chapter/verse and rebuild via `build_bible_url`. Returns None if
    the URL doesn't match. Both start and end triples are honored.
    """
    m = _JWPUB_BIBLE_RE.search(url)
    if not m:
        return None
    sb, sc, sv, eb, ec, ev = (int(g) for g in m.groups())
    end_chapter = ec if ec != sc else None
    end_book = eb if eb != sb else None
    verse_end = ev if (ev != sv or end_chapter is not None or end_book is not None) else None
    return build_bible_url(
        sb,
        sc,
        sv,
        verse_end=verse_end,
        end_chapter=end_chapter,
        end_book=end_book,
        wtlocale=wtlocale,
    )


def convert_jwpub_publication_url(url: str, *, wtlocale: str | None = None) -> str | None:
    """Convert a `jwpub://p/LOCALE:DOCID[/PAR]` URL to `jwlibrary://`.

    Example input:  `jwpub://p/E:1102021201/2`
    Example output: `jwlibrary:///finder?wtlocale=E&docid=1102021201&par=2`

    `wtlocale` override: if given, replaces the locale embedded in the URL.
    """
    m = _JWPUB_PUB_RE.search(url)
    if not m:
        return None
    locale = wtlocale or m.group("locale")
    try:
        docid = int(m.group("docid"))
    except ValueError:
        return None
    par_raw = m.group("par")
    par = int(par_raw) if par_raw else None
    return build_publication_url(docid, paragraph=par, wtlocale=locale)


# ── Render: BibleRef → markdown ───────────────────────────────────────


def _book_display_name(
    book_num: int,
    *,
    language: str,
    length: NameLength,
) -> str:
    """Look up a book's display name in the requested language and length.

    Falls back through: requested ISO → JW code locale → English long.
    """
    try:
        lang = get_language(language)
        jw_code = lang.jw_code
    except KeyError:
        jw_code = get_book_language(language)  # sign-lang → spoken or pass-through

    # Resolve sign-language to its spoken base for book names.
    jw_code_for_books = get_book_language(jw_code) or jw_code

    books = load_book_locale(jw_code_for_books) or load_book_locale("E")
    for b in books:
        if b.book_num == book_num:
            if length == "long" and b.name_long:
                return b.name_long
            if length == "medium" and b.name_medium:
                return b.name_medium
            if length == "short" and b.name_short:
                return b.name_short
            return b.name_long or b.name_medium or b.name_short
    return _canonical_name(book_num)


def _format_reference_text(
    ref: BibleRef,
    *,
    language: str,
    length: NameLength,
) -> str:
    """Render the human label, e.g. 'Juan 3:16' or 'Gén. 1:1-3'."""
    name = _book_display_name(ref.book_num, language=language, length=length)
    if ref.verse_start is None:
        return f"{name} {ref.chapter}"
    if ref.verse_end is None or ref.verse_end == ref.verse_start:
        return f"{name} {ref.chapter}:{ref.verse_start}"
    return f"{name} {ref.chapter}:{ref.verse_start}-{ref.verse_end}"


def render_markdown_link(
    ref: BibleRef,
    *,
    text: str | None = None,
    length: NameLength = "medium",
    language: str | None = None,
    wtlocale: str | None = None,
) -> str:
    """Render a `BibleRef` as `[label](jwlibrary:///finder?bible=…)`.

    `text` overrides the auto-generated label. `language` controls the
    locale used for the auto label (falls back to `ref.detected_language`
    and then English). `wtlocale` is the URL parameter pin; when omitted
    we derive it from `language` so the app opens the link in the same
    language as the label.
    """
    lang = language or ref.detected_language or "en"
    label = text if text is not None else _format_reference_text(ref, language=lang, length=length)
    locale = wtlocale if wtlocale is not None else lang
    url = build_bible_url(
        ref.book_num,
        ref.chapter,
        ref.verse_start,
        verse_end=ref.verse_end,
        wtlocale=locale,
    )
    return f"[{label}]({url})"


# ── Linkify: detect refs in plain text and wrap them ──────────────────


_MARKDOWN_LINK_RE = re.compile(r"\[[^\]]*\]\([^)]*\)")
_FENCED_CODE_RE = re.compile(r"```.*?```", flags=re.DOTALL)
_INLINE_CODE_RE = re.compile(r"`[^`]*`")


@dataclass
class LinkifyResult:
    """What `linkify_markdown` returned — text + diff stats."""

    text: str
    converted: int
    skipped_already_linked: int

    def to_dict(self) -> dict:
        return {
            "text": self.text,
            "converted": self.converted,
            "skipped_already_linked": self.skipped_already_linked,
        }


def _segment_text(text: str) -> list[tuple[str, bool]]:
    """Split into (segment, is_inert) where inert segments must be untouched.

    Inert means: inside a fenced code block, inline code span, or an
    existing markdown link. We linkify only the active segments.
    """
    n = len(text)
    spans: list[tuple[int, int]] = []
    for pattern in (_FENCED_CODE_RE, _MARKDOWN_LINK_RE, _INLINE_CODE_RE):
        for m in pattern.finditer(text):
            spans.append(m.span())
    spans.sort()
    # Merge overlapping spans.
    merged: list[tuple[int, int]] = []
    for s, e in spans:
        if merged and s <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], e))
        else:
            merged.append((s, e))
    out: list[tuple[str, bool]] = []
    cur = 0
    for s, e in merged:
        if s > cur:
            out.append((text[cur:s], False))
        out.append((text[s:e], True))
        cur = e
    if cur < n:
        out.append((text[cur:n], False))
    return out


def _norm_with_offsets(text: str) -> tuple[str, list[int]]:
    """Lowercase + NFD-strip accents, keeping a map back to the original.

    Returns `(normalized, offsets)` where `offsets[i]` is the index in
    `text` that produced `normalized[i]`. Length of `normalized` may
    differ from `text` because combining marks are dropped.
    """
    norm_chars: list[str] = []
    offsets: list[int] = []
    for orig_idx, ch in enumerate(text):
        for nc in unicodedata.normalize("NFD", ch.lower()):
            if unicodedata.combining(nc):
                continue
            norm_chars.append(nc)
            offsets.append(orig_idx)
    return "".join(norm_chars), offsets


def _norm_span_to_original(
    offsets: list[int],
    n_start: int,
    n_end: int,
    *,
    original_length: int,
) -> tuple[int, int]:
    """Map a (start, end) span from the normalized text back to the original."""
    if not offsets:
        return 0, 0
    start = offsets[n_start] if 0 <= n_start < len(offsets) else original_length
    # `end` is exclusive in the normalized space; pick the original index of
    # the last consumed normalized char + 1 to cover its full codepoint.
    last = n_end - 1
    end = offsets[last] + 1 if 0 <= last < len(offsets) else original_length
    return start, end


def linkify_markdown(
    text: str,
    *,
    language: str = "en",
    length: NameLength = "medium",
    wtlocale: str | None = None,
) -> LinkifyResult:
    """Scan `text` and wrap every Bible reference as a `jwlibrary://` link.

    Skips matches that are already inside a markdown link `[…](…)`, inside
    fenced code blocks (``` … ```), and inside inline code spans (`…`).

    Args:
        text: Source markdown.
        language: ISO of the references (used to resolve labels).
        length: Name length to use for the rendered label.
        wtlocale: Optional override for the `wtlocale=` URL parameter.

    Returns a `LinkifyResult` with the rewritten text + counters.
    """
    if not text:
        return LinkifyResult(text=text, converted=0, skipped_already_linked=0)

    parser = _singleton()
    regex = parser._regex
    index = parser._index

    converted = 0
    skipped = 0
    out_parts: list[str] = []

    for chunk, inert in _segment_text(text):
        if inert:
            if chunk.startswith("[") and "jwlibrary://" in chunk:
                skipped += 1
            out_parts.append(chunk)
            continue
        normalized, offsets = _norm_with_offsets(chunk)
        matches = list(regex.finditer(normalized))
        if not matches:
            out_parts.append(chunk)
            continue

        # Replace from the end backwards so earlier original positions
        # stay valid as we splice.
        rewritten = chunk
        for m in reversed(matches):
            from jw_core.parsers.reference import _norm_key

            entry = index.get(_norm_key(m.group("book")))
            if entry is None:
                continue
            book_num, lang_iso, canonical = entry
            verse_start_raw = m.group("verse_start")
            verse_end_raw = m.group("verse_end")
            ref = BibleRef(
                book_num=book_num,
                book_canonical=canonical,
                chapter=int(m.group("chapter")),
                verse_start=int(verse_start_raw) if verse_start_raw else None,
                verse_end=int(verse_end_raw) if verse_end_raw else None,
                detected_language=lang_iso,
                raw_match=normalized[m.start() : m.end()].strip(),
            )
            orig_start, orig_end = _norm_span_to_original(
                offsets, m.start(), m.end(), original_length=len(chunk)
            )
            original_label = rewritten[orig_start:orig_end]
            link = render_markdown_link(
                ref,
                text=original_label,
                length=length,
                language=language,
                wtlocale=wtlocale,
            )
            rewritten = rewritten[:orig_start] + link + rewritten[orig_end:]
            converted += 1
        out_parts.append(rewritten)

    return LinkifyResult(
        text="".join(out_parts),
        converted=converted,
        skipped_already_linked=skipped,
    )


# ── Convert legacy jwpub:// URLs inside markdown ──────────────────────


@dataclass
class ConversionStats:
    """Counters returned by `convert_jw_links_in_text`."""

    text: str
    bible_converted: int = 0
    publication_converted: int = 0
    untouched: int = 0

    def to_dict(self) -> dict:
        return {
            "text": self.text,
            "bible_converted": self.bible_converted,
            "publication_converted": self.publication_converted,
            "untouched": self.untouched,
            "total_converted": self.bible_converted + self.publication_converted,
        }


_MD_LINK_CAPTURE_RE = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")


def convert_jw_links_in_text(
    text: str,
    *,
    kind: Literal["bible", "publication", "all"] = "all",
    wtlocale: str | None = None,
) -> ConversionStats:
    """Rewrite every `jwpub://b/...` and/or `jwpub://p/...` link inside `text`.

    Only the `(url)` part of `[label](url)` patterns is touched. Labels
    survive verbatim. URLs that already start with `jwlibrary://` pass
    through unchanged (no double-conversion).

    Args:
        text: Source markdown.
        kind: Which kinds to convert ('bible', 'publication', 'all').
        wtlocale: Optional override for the destination URL's locale.
    """
    stats = ConversionStats(text=text)
    if not text:
        return stats

    def repl(match: re.Match[str]) -> str:
        label, url = match.group(1), match.group(2)
        if url.startswith("jwpub://b/") and kind in ("bible", "all"):
            converted = convert_jwpub_bible_url(url, wtlocale=wtlocale)
            if converted:
                stats.bible_converted += 1
                return f"[{label}]({converted})"
        if url.startswith("jwpub://p/") and kind in ("publication", "all"):
            converted = convert_jwpub_publication_url(url, wtlocale=wtlocale)
            if converted:
                stats.publication_converted += 1
                return f"[{label}]({converted})"
        stats.untouched += 1
        return match.group(0)

    stats.text = _MD_LINK_CAPTURE_RE.sub(repl, text)
    return stats


# ── Render verse with quote template ──────────────────────────────────


def render_verse_block(
    ref: BibleRef,
    verse_text: str = "",
    *,
    template: QuoteTemplate = "callout",
    length: NameLength = "medium",
    language: str | None = None,
    wtlocale: str | None = None,
) -> str:
    """Return a markdown block that combines a deep link with the verse text.

    Templates (chosen by `template`):

      - `plain`:              `Juan 3:16  Porque tanto amó Dios…`
      - `link`:               `[Juan 3:16](jwlibrary://…)\\n\\n> Porque tanto amó Dios…`
      - `blockquote`:         `> [Juan 3:16](jwlibrary://…)\\n>\\n> Porque tanto amó Dios…`
      - `callout`:            `> [!quote] [Juan 3:16](jwlibrary://…)\\n> Porque tanto amó Dios…`
      - `callout-collapsed`:  `> [!quote]- [Juan 3:16](…)\\n> Porque tanto amó Dios…`

    `verse_text` may be empty — useful when the agent only has the
    reference and wants a stub the user can fill in later.
    """
    link = render_markdown_link(
        ref, length=length, language=language, wtlocale=wtlocale,
    )
    body = (verse_text or "").strip()
    if template == "plain":
        label = _format_reference_text(
            ref,
            language=(language or ref.detected_language or "en"),
            length=length,
        )
        return f"{label}  {body}".rstrip()
    if template == "link":
        return f"{link}\n\n> {body}" if body else link
    if template == "blockquote":
        if body:
            return f"> {link}\n>\n> {body}"
        return f"> {link}"
    if template == "callout":
        return f"> [!quote] {link}\n> {body}" if body else f"> [!quote] {link}"
    if template == "callout-collapsed":
        return f"> [!quote]- {link}\n> {body}" if body else f"> [!quote]- {link}"
    raise ValueError(f"Unknown template: {template!r}")
