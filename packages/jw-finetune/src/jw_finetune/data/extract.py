"""Extract ParagraphRecord from JWPUB / EPUB sources.

For F1 we cover the two main local-corpus formats. WOL article scraping
is deferred to F2 (the toolkit already has the clients; the only missing
piece is the adapter that maps article HTML → ParagraphRecord).

Language detection:
    JWPUB exposes a MEPS integer index in metadata, not an ISO code. The
    toolkit's `jw_core.languages` registry is ISO-keyed, so we rely on the
    caller's `language_hint` (which comes from `Recipe.languages[0]` or the
    `SourceSpec.language`). If no hint is provided we fall back to "und".
"""

from __future__ import annotations

import logging
import re
from collections.abc import Iterator
from pathlib import Path

from jw_core.parsers.article import parse_article
from jw_core.parsers.epub import parse_epub
from jw_core.parsers.jwpub import parse_jwpub

from jw_finetune.data.models import ParagraphRecord, PublicationKind

logger = logging.getLogger(__name__)

# Ordered: longer/more-specific prefixes first so "wp" matches before "w".
_PUBCODE_KIND_PREFIXES: tuple[tuple[str, PublicationKind], ...] = (
    ("nwt", "bible"),
    ("wp", "watchtower"),
    ("ws", "watchtower"),
    ("w", "watchtower"),
    ("g", "awake"),
    ("lff", "book"),
    ("jy", "book"),
    ("sjj", "book"),
    ("bh", "book"),
    ("rr", "book"),
    ("bi", "bible"),
)


def _infer_kind_from_pub_code(pub_code: str) -> PublicationKind:
    """Infer publication kind from the JW symbol/pub_code.

    Conservative: requires the prefix to be followed by digit/underscore/dash
    or end-of-string, so e.g. "wp23" → watchtower but "wpub_something" → other.
    """
    pc = (pub_code or "").lower().strip()
    if not pc:
        return "other"
    for prefix, kind in _PUBCODE_KIND_PREFIXES:
        if pc == prefix or pc.startswith(prefix):
            tail = pc[len(prefix):]
            if not tail or tail[0].isdigit() or tail[0] in "_-":
                return kind
    return "other"


def _clean_paragraph(text: str) -> str:
    """Collapse whitespace, strip."""
    return re.sub(r"\s+", " ", text).strip()


def _derive_pub_code_from_title(title: str) -> str:
    """Best-effort: EPUB titles often don't expose a clean symbol; use heuristics."""
    if not title:
        return "unknown"
    t = title.lower()
    if "atalaya" in t or "watchtower" in t:
        return "w"
    if "despertad" in t or "awake" in t:
        return "g"
    return "book"


def extract_from_epub(
    path: Path | str,
    *,
    language_hint: str = "",
    pub_code_hint: str = "",
    min_chars: int = 30,
) -> Iterator[ParagraphRecord]:
    """Yield one `ParagraphRecord` per non-trivial paragraph in the EPUB.

    Args:
        path: Path to the .epub file.
        language_hint: ISO 639-1 code; overrides EPUB metadata when given.
        pub_code_hint: Manual pub_code; overrides title-based heuristic.
        min_chars: Paragraphs shorter than this are skipped (boilerplate).
    """
    epub = parse_epub(path)
    lang = ((language_hint or epub.language or "und").lower())[:2]
    pub_code = pub_code_hint or _derive_pub_code_from_title(epub.title)
    kind = _infer_kind_from_pub_code(pub_code)

    for doc in epub.documents:
        for i, raw in enumerate(doc.paragraphs):
            text = _clean_paragraph(raw)
            if len(text) < min_chars:
                continue
            yield ParagraphRecord(
                text=text,
                pub_code=pub_code,
                language=lang,
                kind=kind,
                source_path=str(path),
                doc_id=doc.id,
                section_ref=f"{pub_code} {doc.title or doc.id} p.{i + 1}",
                paragraph_pid=None,
                spine_index=doc.spine_index,
                extra={
                    "epub_title": doc.title,
                    "creator": epub.creator,
                },
            )


async def extract_from_wol_article(
    url: str,
    *,
    language_hint: str = "",
    pub_code_hint: str = "",
    publication_kind_hint: PublicationKind | None = None,
    min_chars: int = 30,
    wol_client: object | None = None,
) -> list[ParagraphRecord]:
    """Fetch a WOL article and yield ParagraphRecords.

    Returns a list (not an async iterator) for simplicity. The caller passes
    an optional pre-built `WOLClient` to share connection pooling; if None
    we create a one-shot client and close it.

    The function relies on `jw_core.clients.wol.WOLClient` which provides
    cache/throttle/auth; we don't reimplement HTTP here.
    """
    from jw_core.clients.wol import WOLClient

    owned = False
    if wol_client is None:
        wol_client = WOLClient()
        owned = True
    try:
        # Most WOL pages don't have a one-call "get_article(url)"; the
        # client has `fetch(url)` for raw HTML.
        html = await wol_client.fetch(url)  # type: ignore[attr-defined]
    finally:
        if owned:
            await wol_client.aclose()  # type: ignore[attr-defined]

    article = parse_article(html)
    lang = (language_hint or "und").lower()[:2]
    pub_code = pub_code_hint or _derive_pub_code_from_title(article.title)
    kind = publication_kind_hint or _infer_kind_from_pub_code(pub_code)

    records: list[ParagraphRecord] = []
    for i, raw in enumerate(article.paragraphs):
        text = _clean_paragraph(raw)
        if len(text) < min_chars:
            continue
        records.append(
            ParagraphRecord(
                text=text,
                pub_code=pub_code,
                language=lang,
                kind=kind,
                source_path=url,
                doc_id="",
                section_ref=f"{pub_code} {article.title} p.{i + 1}",
                paragraph_pid=None,
                extra={"article_title": article.title},
            )
        )
    return records


def extract_from_jwpub(
    path: Path | str,
    *,
    language_hint: str = "",
    min_chars: int = 30,
) -> Iterator[ParagraphRecord]:
    """Yield one `ParagraphRecord` per paragraph from a (decrypted) JWPUB.

    Raises:
        FileNotFoundError: If the file does not exist.

    The JWPUB parser will emit a warning and return an empty document list
    if the file uses an unsupported encryption variant.
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(p)

    meta = parse_jwpub(p)
    if not meta.decrypted_text_available:
        logger.warning(
            "JWPUB %s could not be decrypted; no paragraphs yielded.", p
        )
        return

    pub_code = meta.symbol or "unknown"
    kind = _infer_kind_from_pub_code(pub_code)
    # JWPUB exposes MEPS integer index; we don't have a MEPS→ISO map in
    # jw-core. Trust the caller's hint, default to "und".
    lang = (language_hint or "und").lower()[:2]

    for doc in meta.documents:
        for i, raw in enumerate(doc.paragraphs):
            text = _clean_paragraph(raw)
            if len(text) < min_chars:
                continue
            yield ParagraphRecord(
                text=text,
                pub_code=pub_code,
                language=lang,
                kind=kind,
                source_path=str(p),
                doc_id=str(doc.meps_document_id),
                section_ref=(
                    f"{pub_code} {doc.title or doc.toc_title or doc.document_id}"
                    f" p.{i + 1}"
                ),
                paragraph_pid=None,
                extra={
                    "chapter_number": str(doc.chapter_number or 0),
                    "meps_language_index": str(meta.language_index),
                    "jwpub_symbol": meta.symbol,
                },
            )
