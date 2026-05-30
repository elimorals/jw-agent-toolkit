"""Extract one chapter of a study book.

Two paths:
  1) JWPUB local: looks up the publication via `meps_catalog`, decrypts
     with `parsers.jwpub.parse_jwpub`, picks the document by chapter
     number (1-based, matches the JW Library TOC).
  2) WOL fallback: when no local JWPUB is registered, fetches the
     publication page from wol.jw.org via `WOLClient`.

Returns a plain `LessonContent` dataclass — the agent layer wraps this
in `Finding`/`AgentResult` shape.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from jw_core.data.study_books import get_book


class LessonExtractionError(RuntimeError):
    pass


SourceKind = Literal["jwpub_local", "wol_fallback"]


@dataclass(frozen=True)
class LessonContent:
    pub_code: str
    chapter: int
    language: str
    title: str
    paragraphs: list[str]
    scripture_refs: dict[int, list[str]] = field(default_factory=dict)  # paragraph_idx → refs
    source: SourceKind = "wol_fallback"
    citation_url: str = ""


def extract_lesson(pub_code: str, chapter: int, language: str = "es") -> LessonContent:
    """Load one lesson. Raise `LessonExtractionError` on validation errors."""

    try:
        book = get_book(pub_code)
    except KeyError as e:
        raise LessonExtractionError(str(e)) from e

    if not (1 <= chapter <= book.total_chapters):
        raise LessonExtractionError(
            f"chapter={chapter} out of range for {pub_code} (1..{book.total_chapters})"
        )
    if language not in book.languages:
        raise LessonExtractionError(
            f"language={language!r} not supported for {pub_code} (supported: {book.languages})"
        )

    jwpub_path = _find_jwpub_path(symbol=book.jwpub_symbol, language=language)
    if jwpub_path is not None:
        return _extract_from_jwpub(book, chapter, language, jwpub_path)

    return _extract_from_wol(book, chapter, language)


def _find_jwpub_path(*, symbol: str, language: str):
    """Stub: lazy-imports MEPS catalog. Returns Path | None."""

    try:
        from jw_core.integrations.meps_catalog import find_publication_path
    except ImportError:
        return None
    return find_publication_path(symbol=symbol, language=language)


def _extract_from_jwpub(book, chapter, language, path) -> LessonContent:
    """Decrypt JWPUB and pick the requested chapter's document."""

    from jw_core.parsers.jwpub import parse_jwpub

    pub = parse_jwpub(path)
    documents = list(pub.documents)
    if not (1 <= chapter <= len(documents)):
        raise LessonExtractionError(
            f"jwpub for {book.pub_code}/{language} only has {len(documents)} documents"
        )
    doc = documents[chapter - 1]
    title = doc.title or book.title_by_lang.get(language, book.pub_code)
    paragraphs = list(doc.paragraphs)
    refs = _collect_scripture_refs(paragraphs)
    return LessonContent(
        pub_code=book.pub_code,
        chapter=chapter,
        language=language,
        title=title,
        paragraphs=paragraphs,
        scripture_refs=refs,
        source="jwpub_local",
        citation_url=_canonical_url(book.pub_code, chapter, language),
    )


def _extract_from_wol(book, chapter, language) -> LessonContent:
    """Fetch the chapter page from WOL and normalize to LessonContent."""

    page = _fetch_chapter_from_wol(book.pub_code, chapter, language)
    return LessonContent(
        pub_code=book.pub_code,
        chapter=chapter,
        language=language,
        title=getattr(page, "title", "") or book.title_by_lang.get(language, book.pub_code),
        paragraphs=list(getattr(page, "paragraphs", []) or []),
        scripture_refs=_collect_scripture_refs(list(getattr(page, "paragraphs", []) or [])),
        source="wol_fallback",
        citation_url=_canonical_url(book.pub_code, chapter, language),
    )


def _fetch_chapter_from_wol(pub_code: str, chapter: int, language: str):
    """Lazy import — never touch network at import time."""

    from jw_core.clients.factory import build_clients

    suite = build_clients()
    return suite.wol.get_publication_page(pub_code, n=chapter, language=language)


def _collect_scripture_refs(paragraphs: list[str]) -> dict[int, list[str]]:
    try:
        from jw_core.parsers.reference import parse_all_references as _find_refs
    except ImportError:  # pragma: no cover
        _find_refs = None

    refs: dict[int, list[str]] = {}
    for i, p in enumerate(paragraphs, start=1):
        try:
            hits = _find_refs(p) if _find_refs is not None else []
            refs[i] = [str(h) for h in hits] if hits else []
        except Exception:
            refs[i] = []
    return refs


def _canonical_url(pub_code: str, chapter: int, language: str) -> str:
    iso = {"es": "es", "en": "en", "pt": "pt"}.get(language, language)
    return f"https://wol.jw.org/{iso}/wol/publication/r4/lp-{iso[:1]}/{pub_code}/{chapter}"
