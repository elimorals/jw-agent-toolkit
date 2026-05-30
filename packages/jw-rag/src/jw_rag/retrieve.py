"""Retrieval helpers — thin convenience wrappers over VectorStore.

For most callers `store.hybrid_search(query)` is enough. This module exposes
a couple of small utilities for chaining retrieval with downstream logic
(e.g. ranking by recency, deduping by source_id).
"""

from __future__ import annotations

from collections.abc import Iterable

from jw_rag.store import SearchHit


def dedup_by_source(hits: Iterable[SearchHit]) -> list[SearchHit]:
    """Keep only the highest-ranked hit per source_id."""
    seen: set[str] = set()
    out: list[SearchHit] = []
    for hit in hits:
        sid = hit.chunk.source_id
        if sid in seen:
            continue
        seen.add(sid)
        out.append(hit)
    return out


def filter_by_metadata(
    hits: Iterable[SearchHit], **eq_filters: object
) -> list[SearchHit]:
    """Filter hits whose chunk.metadata matches all `eq_filters` exactly."""
    def matches(hit: SearchHit) -> bool:
        return all(hit.chunk.metadata.get(k) == v for k, v in eq_filters.items())
    return [h for h in hits if matches(h)]
