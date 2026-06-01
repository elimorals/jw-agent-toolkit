"""SemanticChunker — heuristic continuation/closure-marker chunker.

Pipeline:
  1) Resolve language: metadata["language"] > detect_language(joined_text)
     > None → fall back to ParagraphChunker.
  2) Continuation merge: paragraphs starting with a continuation marker
     glue onto the open chunk, up to max_chars * (1 + continuation_overflow).
     After max_continuation_merges consecutive merges, force flush.
  3) Closure split: paragraphs starting with a closure marker append, then
     flush if min_chars satisfied.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from jw_rag.chunkers.markers import (
    detect_language,
    is_closure_start,
    is_continuation_start,
    load_markers,
)
from jw_rag.chunkers.paragraph_chunker import Chunk, ParagraphChunker


@dataclass
class _OpenChunk:
    paragraphs: list[str] = field(default_factory=list)
    para_ids: list[int] = field(default_factory=list)
    merge_reason: str | None = None
    closure_marker: str | None = None
    continuation_merges_in_a_row: int = 0

    @property
    def total_len(self) -> int:
        return sum(len(p) for p in self.paragraphs)

    def append(self, paragraph: str, index: int, *, merge_reason: str | None = None) -> None:
        self.paragraphs.append(paragraph)
        self.para_ids.append(index)
        if merge_reason and self.merge_reason is None:
            self.merge_reason = merge_reason


class SemanticChunker:
    name = "semantic"

    def __init__(
        self,
        *,
        max_chars: int = 1500,
        min_chars: int = 80,
        continuation_overflow: float = 0.30,
        max_continuation_merges: int = 2,
    ) -> None:
        self.max_chars = max_chars
        self.min_chars = min_chars
        self.continuation_overflow = continuation_overflow
        self.max_continuation_merges = max_continuation_merges
        self._fallback = ParagraphChunker(max_chars=max_chars, min_chars=min_chars)

    def chunk(
        self,
        paragraphs: list[str],
        source_id: str,
        *,
        metadata: dict[str, Any] | None = None,
    ) -> list[Chunk]:
        base_meta = dict(metadata or {})
        cleaned = [p.strip() for p in paragraphs if p and p.strip()]
        if not cleaned:
            return []

        language = base_meta.get("language")
        detected: str | None = None
        if not language:
            joined = " ".join(cleaned[:5])
            detected = detect_language(joined)
            language = detected
        elif language not in load_markers():
            base_meta = {**base_meta, "mixed_language": True}
            return self._fallback_chunks(cleaned, source_id, base_meta)

        if language is None:
            return self._fallback_chunks(cleaned, source_id, base_meta)

        base_meta["language_detected"] = detected or language
        return self._chunk_semantic(cleaned, source_id, base_meta, language)

    def _fallback_chunks(
        self,
        paragraphs: list[str],
        source_id: str,
        base_meta: dict[str, Any],
    ) -> list[Chunk]:
        chunks = self._fallback.chunk(paragraphs, source_id, metadata=base_meta)
        for c in chunks:
            c.metadata["chunker"] = "semantic"
            c.metadata.setdefault("merge_reason", None)
            c.metadata.setdefault("closure_marker", None)
            c.metadata.setdefault("para_ids", [])
        return chunks

    def _chunk_semantic(
        self,
        paragraphs: list[str],
        source_id: str,
        base_meta: dict[str, Any],
        language: str,
    ) -> list[Chunk]:
        out: list[Chunk] = []
        open_chunk = _OpenChunk()

        def flush() -> None:
            nonlocal open_chunk
            if not open_chunk.paragraphs:
                return
            text = " ".join(open_chunk.paragraphs).strip()
            if text:
                meta = {
                    **base_meta,
                    "chunker": "semantic",
                    "merge_reason": open_chunk.merge_reason,
                    "closure_marker": open_chunk.closure_marker,
                    "para_ids": list(open_chunk.para_ids),
                    "para_count": len(open_chunk.paragraphs),
                }
                out.append(
                    Chunk(
                        id=f"{source_id}#{len(out)}",
                        text=text,
                        source_id=source_id,
                        metadata=meta,
                    )
                )
            open_chunk = _OpenChunk()

        overflow_limit = int(self.max_chars * (1 + self.continuation_overflow))

        def _next_is_continuation(i: int) -> bool:
            if i + 1 >= len(paragraphs):
                return False
            return is_continuation_start(paragraphs[i + 1], language)

        def _next_is_closure(i: int) -> bool:
            if i + 1 >= len(paragraphs):
                return False
            return is_closure_start(paragraphs[i + 1], language)

        for idx, paragraph in enumerate(paragraphs):
            if len(paragraph) > self.max_chars:
                flush()
                for piece in _split_long(paragraph, self.max_chars):
                    out.append(
                        Chunk(
                            id=f"{source_id}#{len(out)}",
                            text=piece,
                            source_id=source_id,
                            metadata={
                                **base_meta,
                                "chunker": "semantic",
                                "split": True,
                                "para_ids": [idx],
                            },
                        )
                    )
                continue

            if (
                open_chunk.paragraphs
                and is_continuation_start(paragraph, language)
                and open_chunk.continuation_merges_in_a_row < self.max_continuation_merges
                and open_chunk.total_len + len(paragraph) <= overflow_limit
            ):
                open_chunk.append(paragraph, idx, merge_reason="continuation_marker")
                open_chunk.continuation_merges_in_a_row += 1
                continue

            if (
                open_chunk.paragraphs
                and is_continuation_start(paragraph, language)
                and open_chunk.continuation_merges_in_a_row >= self.max_continuation_merges
            ):
                flush()

            if is_closure_start(paragraph, language):
                open_chunk.append(paragraph, idx)
                open_chunk.closure_marker = _matched_closure_marker(paragraph, language)
                if open_chunk.total_len >= self.min_chars:
                    flush()
                continue

            open_chunk.append(paragraph, idx)
            open_chunk.continuation_merges_in_a_row = 0
            if open_chunk.total_len >= self.max_chars:
                flush()
            elif (
                open_chunk.total_len >= self.min_chars
                and paragraph.endswith((".", "!", "?"))
                and not _next_is_continuation(idx)
                and not _next_is_closure(idx)
            ):
                flush()

        flush()
        return out


def _split_long(text: str, max_chars: int) -> list[str]:
    out: list[str] = []
    current = ""
    for sentence in _sentences(text):
        if len(current) + len(sentence) + 1 > max_chars and current:
            out.append(current.strip())
            current = sentence
        else:
            current = (current + " " + sentence).strip()
    if current:
        out.append(current.strip())
    final: list[str] = []
    for s in out:
        while len(s) > max_chars:
            final.append(s[:max_chars])
            s = s[max_chars:]
        if s:
            final.append(s)
    return final


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


def _matched_closure_marker(paragraph: str, language: str) -> str | None:
    ms = load_markers().get(language)
    if ms is None:
        return None
    stripped = paragraph.lstrip()
    for m in ms.closure:
        if stripped.startswith(m):
            return m
    return None
