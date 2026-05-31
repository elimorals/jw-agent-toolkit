"""Three-way RRF: bm25 + text-vector + visual-MaxSim.

If `visual_store is None` or `visual_store.is_empty`, the function is
equivalent to `text_store.hybrid_search(query, ...)`. That makes it safe to
call unconditionally from agents and from `jw rag search` — there's no
"branch on visual enabled" logic to forget.

RRF formula (same as Fase 33):
    score(doc) = Σ_ranklist 1 / (rrf_k + rank_in_list)

Visual hits enter the same dict keyed by `chunk.id`. Text and visual IDs
follow different conventions (`{chunk_idx}` vs `{source_id}#p{N}`) so there's
no accidental collision.
"""

from __future__ import annotations

from typing import Any

from jw_rag.store import SearchHit, VectorStore
from jw_rag.visual.visual_store import VisualVectorStore


def hybrid_search_with_visual(
    text_store: VectorStore,
    visual_store: VisualVectorStore | None,
    query: str,
    *,
    top_k: int = 10,
    candidate_pool: int = 50,
    rrf_k: int = 60,
) -> list[SearchHit]:
    """Three-way RRF across bm25, text-vector, and visual-MaxSim.

    When `visual_store` is None or empty, behaves identically to
    `text_store.hybrid_search(query, top_k=top_k, candidate_pool=candidate_pool,
    rrf_k=rrf_k)`.
    """
    if visual_store is None or visual_store.is_empty:
        return text_store.hybrid_search(query, top_k=top_k, candidate_pool=candidate_pool, rrf_k=rrf_k)

    vec_hits = text_store.vector_search(query, top_k=candidate_pool)
    bm25_hits = text_store.bm25_search(query, top_k=candidate_pool)
    visual_hits = visual_store.search(query, top_k=candidate_pool)

    fused: dict[str, tuple[float, Any, str]] = {}
    # source label preference: visual wins if any list ranked the doc as visual
    for hits in (vec_hits, bm25_hits):
        for hit in hits:
            contribution = 1.0 / (rrf_k + hit.rank)
            prev = fused.get(hit.chunk.id)
            if prev is None:
                fused[hit.chunk.id] = (contribution, hit.chunk, "hybrid")
            else:
                fused[hit.chunk.id] = (prev[0] + contribution, prev[1], prev[2])
    for hit in visual_hits:
        contribution = 1.0 / (rrf_k + hit.rank)
        prev = fused.get(hit.chunk.id)
        if prev is None:
            fused[hit.chunk.id] = (contribution, hit.chunk, "visual")
        else:
            # Bump score, prefer the visual chunk object so callers can render.
            fused[hit.chunk.id] = (prev[0] + contribution, hit.chunk, "visual")

    ordered = sorted(fused.values(), key=lambda t: -t[0])[:top_k]
    return [
        SearchHit(chunk=chunk, score=float(score), rank=r, source=src)
        for r, (score, chunk, src) in enumerate(ordered, 1)
    ]
