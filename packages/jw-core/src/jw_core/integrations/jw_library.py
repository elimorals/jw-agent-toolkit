"""Deep links into the official JW Library desktop/mobile app.

JW Library registers a custom URL scheme `jwlibrary://` on every platform it
supports (UWP on Windows, iPad-app on macOS Apple Silicon, native on iOS and
Android). Activating one of these URLs is the only stable, officially
sanctioned way for a third-party process to make JW Library navigate to a
specific verse or publication. This module builds and dispatches them.

URL scheme (verified against `msakowski/obsidian-library-linker`):

    jwlibrary:///finder?bible=BBCCCVVV[-BBCCCVVV][&wtlocale=LL]
    jwlibrary:///finder?docid=N[&par=P][&wtlocale=LL]

  BB = book number (1..66), padded to 2 digits ("01".."66").
  CCC = chapter, padded to 3 digits ("001".."150").
  VVV = verse, padded to 3 digits ("001".."176").
  LL = JW language code (E/S/T/F/X/I/J/U/CHS/KO/...).

For a single verse, end == start (or pass `verse_end=None` and we expand to
the single-verse form). For multi-chapter ranges, pass `end_chapter` and
`verse_end` so we emit a `-` separator with the end book/chapter/verse.

Disjoint verses (e.g. Juan 1:1, 4, 7) cannot be expressed in a single
`jwlibrary://` URL; the upstream Obsidian plugin returns one URL per range
in that case. We mirror that contract via `build_bible_urls()` (plural).
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from jw_core.languages import get_language

if TYPE_CHECKING:
    from jw_core.models import BibleRef

__all__ = [
    "JWLibraryError",
    "VerseRange",
    "build_bible_url",
    "build_bible_urls",
    "build_publication_url",
    "build_url_for_ref",
    "detect_platform",
    "open_jw_library",
]

logger = logging.getLogger(__name__)

# Bible reference padding widths, matched 1:1 to the JW Library URL scheme.
_BOOK_PAD = 2
_CHAPTER_PAD = 3
_VERSE_PAD = 3

# Books 1..66 are valid (Genesis..Revelation). Books outside this range are
# not addressable via `?bible=`; callers must use `?docid=` instead.
_MIN_BOOK = 1
_MAX_BOOK = 66

# Chapter/verse upper bound is enforced loosely (Psalm 119 has 176 verses,
# Psalms book has 150 chapters). We accept anything in the printable range
# rather than embed a per-book table — JW Library will simply not navigate
# if the address is out of bounds.
_MIN_NUM = 1
_MAX_NUM = 999


class JWLibraryError(RuntimeError):
    """Raised when a JW Library deep link cannot be built or dispatched."""


@dataclass(frozen=True)
class VerseRange:
    """One contiguous verse range. `end` equals `start` for a single verse."""

    start: int
    end: int

    def __post_init__(self) -> None:
        if not _MIN_NUM <= self.start <= _MAX_NUM:
            raise JWLibraryError(f"start verse out of range: {self.start}")
        if not _MIN_NUM <= self.end <= _MAX_NUM:
            raise JWLibraryError(f"end verse out of range: {self.end}")
        if self.end < self.start:
            raise JWLibraryError(f"end ({self.end}) precedes start ({self.start})")


@dataclass(frozen=True)
class _BibleAddress:
    """Internal triple addressing a single padded BBCCCVVV token."""

    book: int
    chapter: int
    verse: int

    def encode(self) -> str:
        return f"{self.book:0{_BOOK_PAD}d}{self.chapter:0{_CHAPTER_PAD}d}{self.verse:0{_VERSE_PAD}d}"


def _validate_book(book: int) -> None:
    if not _MIN_BOOK <= book <= _MAX_BOOK:
        raise JWLibraryError(f"book_num must be {_MIN_BOOK}..{_MAX_BOOK}, got {book}")


def _validate_num(value: int, label: str) -> None:
    if not _MIN_NUM <= value <= _MAX_NUM:
        raise JWLibraryError(f"{label} must be {_MIN_NUM}..{_MAX_NUM}, got {value}")


def _resolve_wtlocale(value: str | None) -> str | None:
    """Map ISO / JW codes to the canonical `wtlocale` token.

    Accepts ISO codes ("en", "es", "pt"), JW codes ("E", "S", "T"), or None.
    Unknown values are returned as-is so the caller can still emit obscure
    or sign-language locales that aren't in our registry.
    """
    if value is None or value == "":
        return None
    try:
        return get_language(value).jw_code
    except KeyError:
        # Unknown — pass-through so callers can use codes we haven't catalogued.
        return value.upper() if value.isascii() else value


def build_bible_url(
    book_num: int,
    chapter: int,
    verse_start: int | None = None,
    *,
    verse_end: int | None = None,
    end_chapter: int | None = None,
    end_book: int | None = None,
    wtlocale: str | None = None,
) -> str:
    """Return one `jwlibrary:///finder?bible=...` URL.

    Args:
        book_num: 1..66.
        chapter: Chapter number.
        verse_start: First verse. When None, JW Library navigates to the
            chapter start (we encode verse 1 implicitly).
        verse_end: Last verse of the range. When None and `end_chapter` is
            also None, treated as a single-verse link.
        end_chapter: For multi-chapter ranges (e.g. Mateo 3:1-4:11) the
            chapter where the range ends. Must be > `chapter`.
        end_book: For cross-book ranges (very rare). Defaults to `book_num`.
        wtlocale: Optional language pin. Accepts ISO or JW code.

    Returns:
        A single deep-link URL.

    Raises:
        JWLibraryError: If inputs are inconsistent (e.g. end before start).
    """
    _validate_book(book_num)
    _validate_num(chapter, "chapter")
    start_verse = verse_start if verse_start is not None else 1
    _validate_num(start_verse, "verse_start")

    start = _BibleAddress(book=book_num, chapter=chapter, verse=start_verse)

    has_range = verse_end is not None or end_chapter is not None or end_book is not None
    if not has_range:
        return _wrap_bible_token(start.encode(), wtlocale)

    final_end_book = end_book if end_book is not None else book_num
    final_end_chapter = end_chapter if end_chapter is not None else chapter
    final_end_verse = verse_end if verse_end is not None else start_verse

    _validate_book(final_end_book)
    _validate_num(final_end_chapter, "end_chapter")
    _validate_num(final_end_verse, "verse_end")

    if final_end_book < book_num:
        raise JWLibraryError("end_book precedes book_num")
    if final_end_book == book_num:
        if final_end_chapter < chapter:
            raise JWLibraryError("end_chapter precedes chapter")
        if final_end_chapter == chapter and final_end_verse < start_verse:
            raise JWLibraryError("verse_end precedes verse_start within same chapter")

    end = _BibleAddress(book=final_end_book, chapter=final_end_chapter, verse=final_end_verse)
    if start.encode() == end.encode():
        return _wrap_bible_token(start.encode(), wtlocale)
    return _wrap_bible_token(f"{start.encode()}-{end.encode()}", wtlocale)


def build_bible_urls(
    book_num: int,
    chapter: int,
    ranges: list[VerseRange],
    *,
    wtlocale: str | None = None,
) -> list[str]:
    """Return one URL per non-contiguous verse range within a chapter.

    JW Library's `?bible=` parameter does not support disjoint ranges; the
    upstream Obsidian plugin returns an array of URLs in that case and we
    follow the same contract. Use this when the user's reference includes
    commas (e.g. "Juan 1:1,4,7-8").
    """
    if not ranges:
        raise JWLibraryError("ranges must not be empty")
    return [
        build_bible_url(
            book_num,
            chapter,
            r.start,
            verse_end=r.end if r.end != r.start else None,
            wtlocale=wtlocale,
        )
        for r in ranges
    ]


def build_publication_url(
    docid: int | str,
    *,
    paragraph: int | None = None,
    wtlocale: str | None = None,
) -> str:
    """Return `jwlibrary:///finder?wtlocale=LL&docid=N[&par=P]`.

    `docid` is a MEPS document identifier (the same one JW Library uses
    internally). You can derive it for a downloaded `.jwpub` via
    `jw_core.parsers.jwpub.parse_jwpub_metadata`. There is no public
    catalog mapping arbitrary publications to MEPS ids; for content not in
    a `.jwpub` on disk, use a Bible URL instead or hand-resolve via
    wol.jw.org.
    """
    try:
        docid_int = int(docid)
    except (TypeError, ValueError) as e:
        raise JWLibraryError(f"docid must be numeric, got {docid!r}") from e
    if docid_int <= 0:
        raise JWLibraryError(f"docid must be positive, got {docid_int}")

    params: list[tuple[str, str]] = []
    locale = _resolve_wtlocale(wtlocale)
    if locale:
        params.append(("wtlocale", locale))
    params.append(("docid", str(docid_int)))
    if paragraph is not None:
        if paragraph <= 0:
            raise JWLibraryError(f"paragraph must be positive, got {paragraph}")
        params.append(("par", str(paragraph)))

    query = "&".join(f"{k}={v}" for k, v in params)
    return f"jwlibrary:///finder?{query}"


def build_url_for_ref(ref: BibleRef, *, wtlocale: str | None = None) -> str:
    """Convert a parsed `BibleRef` (from `jw_core.parsers.reference`) into a URL.

    Picks up `verse_end` automatically. When neither verse is set, navigates
    to chapter start. When `wtlocale` is None, defaults to the language the
    reference was detected in (so "Juan 3:16" → wtlocale=S by default).
    """
    locale = wtlocale if wtlocale is not None else ref.detected_language
    return build_bible_url(
        ref.book_num,
        ref.chapter,
        ref.verse_start,
        verse_end=ref.verse_end,
        wtlocale=locale,
    )


def _wrap_bible_token(token: str, wtlocale: str | None) -> str:
    locale = _resolve_wtlocale(wtlocale)
    if locale:
        return f"jwlibrary:///finder?bible={token}&wtlocale={locale}"
    return f"jwlibrary:///finder?bible={token}"


# ── Platform dispatch ───────────────────────────────────────────────────


def detect_platform() -> str:
    """Return 'darwin', 'win32', 'linux', or 'unknown'."""
    p = sys.platform
    if p == "darwin":
        return "darwin"
    if p == "win32":
        return "win32"
    if p.startswith("linux"):
        return "linux"
    return "unknown"


@dataclass(frozen=True)
class _OpenCommand:
    """Argv that lands `url` on the OS handler for the `jwlibrary` scheme."""

    argv: list[str]
    use_shell: bool = False
    env: dict[str, str] = field(default_factory=dict)


def _build_open_command(url: str, platform: str) -> _OpenCommand:
    if platform == "darwin":
        return _OpenCommand(argv=["open", url])
    if platform == "win32":
        # `start` is a cmd builtin, so shell=True is unavoidable. We mitigate
        # by validating that `url` starts with the expected scheme — see the
        # check in `open_jw_library`.
        return _OpenCommand(argv=["cmd", "/c", "start", "", url], use_shell=False)
    if platform == "linux":
        # `xdg-open` is the freedesktop standard. App must be installed via
        # wine + protocol handler; we don't promise it works out of the box.
        return _OpenCommand(argv=["xdg-open", url])
    raise JWLibraryError(f"No URL handler available on platform: {platform!r}")


def _assert_safe_jwlibrary_url(url: str) -> None:
    """Defense-in-depth: refuse to dispatch anything that isn't jwlibrary://.

    Stops accidental injection if the caller hands us an attacker-controlled
    string. The validated builders above can never produce a non-jwlibrary
    URL but the dispatcher is also exported for advanced callers.
    """
    if not url.startswith("jwlibrary://"):
        raise JWLibraryError(f"Refusing to dispatch non-jwlibrary URL: {url!r}")
    # Reject control characters that could escape into argv on Windows.
    if any(ord(c) < 0x20 for c in url):
        raise JWLibraryError("URL contains control characters")


def open_jw_library(
    url: str,
    *,
    dry_run: bool = False,
    platform: str | None = None,
    runner: object = subprocess,
) -> dict[str, object]:
    """Open `url` in the user's installed JW Library app.

    Args:
        url: Must start with `jwlibrary://`. Use the `build_*` helpers above
            to make a safe one.
        dry_run: When True, validate and return the URL without launching
            anything. The MCP layer exposes this so a chat client can show
            the link to the user instead of opening it on the server.
        platform: Override platform autodetect (mostly for tests).
        runner: Override `subprocess` (for tests). Must implement `.run()`.

    Returns:
        A dict with `url`, `platform`, `dispatched` (bool), and on success
        `returncode`. On `dry_run`, `dispatched` is False and the return
        contains `dry_run=True`.

    Raises:
        JWLibraryError: If validation fails or the handler is unavailable.
    """
    _assert_safe_jwlibrary_url(url)
    plat = platform or detect_platform()

    if dry_run:
        return {"url": url, "platform": plat, "dispatched": False, "dry_run": True}

    cmd = _build_open_command(url, plat)
    if plat in {"darwin", "linux"} and not shutil.which(cmd.argv[0]):
        raise JWLibraryError(f"Required URL opener {cmd.argv[0]!r} not found on PATH")

    env = {**os.environ, **cmd.env} if cmd.env else None
    logger.info("Dispatching jwlibrary:// deep link via %s", cmd.argv[0])
    try:
        result = runner.run(  # type: ignore[attr-defined]
            cmd.argv,
            check=False,
            capture_output=True,
            text=True,
            env=env,
        )
    except FileNotFoundError as e:
        raise JWLibraryError(f"Could not launch URL opener: {e}") from e
    return {
        "url": url,
        "platform": plat,
        "dispatched": True,
        "returncode": getattr(result, "returncode", 0),
        "stderr": (getattr(result, "stderr", "") or "").strip()[:500],
    }
