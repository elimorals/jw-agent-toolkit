"""Text chunking for the RAG ingest pipeline.

JW content is highly structured — articles are paragraphs with explicit
`data-pid`, Bible chapters are verses. We chunk by paragraph (one paragraph
= one chunk) and merge adjacent short paragraphs to hit a target size.

For Bible text we'd ideally chunk by verse — that's Phase 5 once we have
verse extraction. For now this works for articles and daily texts.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Chunk:
    """A unit of indexed text."""

    id: str
    text: str
    source_id: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


def chunk_paragraphs(
    paragraphs: list[str],
    source_id: str,
    *,
    max_chars: int = 1500,
    min_chars: int = 80,
    metadata: dict[str, Any] | None = None,
) -> list[Chunk]:
    """Turn a list of paragraphs into chunks.

    - Paragraphs shorter than `min_chars` get merged with the next paragraph.
    - Paragraphs longer than `max_chars` get split at sentence boundaries.
    - The chunk id is `{source_id}#{index}`.

    `metadata` is shallow-copied into every chunk so callers can attach
    fields like `book_num`, `chapter`, `pub_code`, etc.
    """
    base_meta = dict(metadata or {})
    chunks: list[Chunk] = []
    buf: list[str] = []
    buf_len = 0

    def flush() -> None:
        nonlocal buf, buf_len
        if buf:
            text = " ".join(buf).strip()
            if text:
                chunks.append(
                    Chunk(
                        id=f"{source_id}#{len(chunks)}",
                        text=text,
                        source_id=source_id,
                        metadata={**base_meta, "para_count": len(buf)},
                    )
                )
            buf = []
            buf_len = 0

    for p in paragraphs:
        p = p.strip()
        if not p:
            continue
        if len(p) > max_chars:
            flush()
            # Split long paragraphs at sentence ends.
            for piece in _split_long(p, max_chars):
                chunks.append(
                    Chunk(
                        id=f"{source_id}#{len(chunks)}",
                        text=piece,
                        source_id=source_id,
                        metadata={**base_meta, "split": True},
                    )
                )
            continue
        buf.append(p)
        buf_len += len(p)
        if buf_len >= max_chars or (buf_len >= min_chars and len(buf) >= 1 and p.endswith((".", "!", "?"))):
            flush()
    flush()
    return chunks


def _split_long(text: str, max_chars: int) -> list[str]:
    """Greedy split at sentence boundaries; falls back to hard cut."""
    sentences = []
    current = ""
    for sentence in _sentences(text):
        if len(current) + len(sentence) + 1 > max_chars and current:
            sentences.append(current.strip())
            current = sentence
        else:
            current = (current + " " + sentence).strip()
    if current:
        sentences.append(current.strip())
    # If anything is still too long, hard-cut.
    out: list[str] = []
    for s in sentences:
        while len(s) > max_chars:
            out.append(s[:max_chars])
            s = s[max_chars:]
        if s:
            out.append(s)
    return out


def _sentences(text: str) -> list[str]:
    """Tiny sentence splitter — good enough for ingest."""
    out: list[str] = []
    current = ""
    for c in text:
        current += c
        if c in ".!?" and len(current) > 4:
            out.append(current.strip())
            current = ""
    if current.strip():
        out.append(current.strip())
    return out
