"""Paragraph chunker — bit-for-bit identical to the legacy
`jw_rag.chunker.chunk_paragraphs`. Single source of truth for `Chunk`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Chunk:
    """A unit of indexed text. Single source of truth — re-exported by
    `jw_rag.chunker` and by `jw_rag.chunkers.__init__`."""

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
    """Legacy free-function API. Kept byte-stable for backcompat."""

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
        if buf_len >= max_chars or (
            buf_len >= min_chars and len(buf) >= 1 and p.endswith((".", "!", "?"))
        ):
            flush()
    flush()
    return chunks


def _split_long(text: str, max_chars: int) -> list[str]:
    sentences: list[str] = []
    current = ""
    for sentence in _sentences(text):
        if len(current) + len(sentence) + 1 > max_chars and current:
            sentences.append(current.strip())
            current = sentence
        else:
            current = (current + " " + sentence).strip()
    if current:
        sentences.append(current.strip())
    out: list[str] = []
    for s in sentences:
        while len(s) > max_chars:
            out.append(s[:max_chars])
            s = s[max_chars:]
        if s:
            out.append(s)
    return out


def _sentences(text: str) -> list[str]:
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


class ParagraphChunker:
    """Wrap the legacy function in a class so it satisfies the Chunker
    Protocol. Behaviour is delegation-only."""

    name = "paragraph"

    def __init__(self, *, max_chars: int = 1500, min_chars: int = 80) -> None:
        self.max_chars = max_chars
        self.min_chars = min_chars

    def chunk(
        self,
        paragraphs: list[str],
        source_id: str,
        *,
        metadata: dict[str, Any] | None = None,
    ) -> list[Chunk]:
        out = chunk_paragraphs(
            paragraphs,
            source_id,
            max_chars=self.max_chars,
            min_chars=self.min_chars,
            metadata=metadata,
        )
        for c in out:
            c.metadata.setdefault("chunker", "paragraph")
        return out
