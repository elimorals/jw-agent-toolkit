"""Chunking adapter — delegates to `jw_rag.chunker.chunk_paragraphs`.

The RAG chunker already implements the right policy: merge short paragraphs,
split long ones at sentence boundaries, attach metadata. We just group
records by source (pub_code, doc_id) so chunks don't cross document
boundaries — that would mix unrelated context.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable

from jw_rag.chunker import Chunk, chunk_paragraphs

from jw_finetune.data.models import ParagraphRecord


def records_to_chunks(
    records: Iterable[ParagraphRecord],
    *,
    max_chars: int = 1500,
    min_chars: int = 80,
) -> list[Chunk]:
    """Group records by (pub_code, doc_id) and chunk each group separately.

    Metadata propagated to each chunk: pub_code, doc_id, language, kind,
    source_path, section_ref. The chunk's `source_id` is `"{pub_code}:{doc_id}"`.
    """
    groups: dict[tuple[str, str], list[ParagraphRecord]] = defaultdict(list)
    for r in records:
        groups[(r.pub_code, r.doc_id or "na")].append(r)

    all_chunks: list[Chunk] = []
    for (pub_code, doc_id), group in groups.items():
        if not group:
            continue
        paragraphs = [r.text for r in group]
        first = group[0]
        chunks = chunk_paragraphs(
            paragraphs,
            source_id=f"{pub_code}:{doc_id}",
            max_chars=max_chars,
            min_chars=min_chars,
            metadata={
                "pub_code": pub_code,
                "doc_id": doc_id,
                "language": first.language,
                "kind": first.kind,
                "source_path": first.source_path,
                "section_ref": first.section_ref,
            },
        )
        all_chunks.extend(chunks)
    return all_chunks
