"""Hybrid search over a VisualIndexer: FTS5 + CLIP cosine + RRF (Fase 69)."""

from __future__ import annotations

import logging

import numpy as np

from jw_core.broadcasting.visual.indexer import VisualIndexer
from jw_core.broadcasting.visual.models import VisualSearchHit
from jw_core.broadcasting.visual.providers import CLIPEncoder

logger = logging.getLogger(__name__)

_RRF_K = 60


def _fts5_search(
    indexer: VisualIndexer,
    *,
    query: str,
    candidate_pool: int = 50,
) -> list[tuple[int, float]]:
    """Return (embedding_id, score) pairs from FTS5 ranking.

    Uses bm25() helper available in SQLite FTS5; lower bm25 = better.
    We invert to keep "higher = better" semantics.
    """
    try:
        cur = indexer.conn.execute(
            "SELECT rowid, bm25(frames_fts) FROM frames_fts "
            "WHERE frames_fts MATCH ? ORDER BY bm25(frames_fts) LIMIT ?",
            (query, candidate_pool),
        )
        rows = list(cur)
    except Exception as exc:  # noqa: BLE001
        logger.debug("FTS5 query failed (%s); empty fts hits.", exc)
        return []
    return [(int(rowid), -float(bm25)) for rowid, bm25 in rows]


def _clip_cosine_top(
    *,
    query_vec: np.ndarray,
    vectors: np.ndarray,
    candidate_pool: int = 50,
) -> list[tuple[int, float]]:
    """Return (rowid_1based, cosine_score) for the top-K most similar frames.

    Assumes `vectors` are L2-normalized (FakeCLIPEncoder + real CLIP
    encoders both return unit vectors).
    """
    if vectors.shape[0] == 0:
        return []
    q = np.asarray(query_vec, dtype=np.float32).reshape(-1)
    qn = np.linalg.norm(q)
    if qn > 0:
        q = q / qn
    sims = vectors @ q
    k = min(candidate_pool, sims.shape[0])
    idx = np.argpartition(-sims, k - 1)[:k]
    ranked = idx[np.argsort(-sims[idx])]
    # Rows are 1-based to match SQLite rowid.
    return [(int(i) + 1, float(sims[i])) for i in ranked]


def _rrf_fuse(
    hit_lists: list[list[tuple[int, float]]],
    *,
    top_k: int = 10,
) -> list[tuple[int, float]]:
    """Reciprocal Rank Fusion. Returns [(rowid, fused_score), ...]."""
    fused: dict[int, float] = {}
    for hits in hit_lists:
        for rank, (rowid, _score) in enumerate(hits):
            fused[rowid] = fused.get(rowid, 0.0) + 1.0 / (_RRF_K + rank)
    ranked = sorted(fused.items(), key=lambda kv: -kv[1])
    return ranked[:top_k]


def _build_deep_link(video_id: str, timestamp_s: float) -> str:
    """Best-effort deep link into tv.jw.org with `#t=<seconds>` anchor."""
    return f"https://tv.jw.org/#t={int(timestamp_s)}&v={video_id}"


def visual_search(
    indexer: VisualIndexer,
    query: str,
    *,
    clip_encoder: CLIPEncoder | None = None,
    top_k: int = 10,
    min_score: float = 0.0,
) -> list[VisualSearchHit]:
    """Search the visual index hybridly. CLIP-cosine is skipped if no encoder."""
    candidate = max(top_k * 5, 20)
    hit_lists: list[list[tuple[int, float]]] = []

    fts_hits = _fts5_search(indexer, query=query, candidate_pool=candidate)
    if fts_hits:
        hit_lists.append(fts_hits)

    if clip_encoder is not None:
        vectors = indexer.load_vectors()
        if vectors.shape[0] > 0:
            qvec = np.asarray(
                clip_encoder.encode_text(query), dtype=np.float32
            )
            clip_hits = _clip_cosine_top(
                query_vec=qvec,
                vectors=vectors,
                candidate_pool=candidate,
            )
            if clip_hits:
                hit_lists.append(clip_hits)

    if not hit_lists:
        return []

    fused = _rrf_fuse(hit_lists, top_k=top_k)
    if not fused:
        return []

    rowids = [rowid for rowid, _ in fused]
    placeholders = ",".join("?" * len(rowids))
    cur = indexer.conn.execute(
        "SELECT embedding_id, video_id, timestamp_s, caption, "
        "thumb_path, transcript_concurrent "
        f"FROM frames WHERE embedding_id IN ({placeholders})",
        rowids,
    )
    row_map = {int(row[0]): row for row in cur}
    hits: list[VisualSearchHit] = []
    for rowid, score in fused:
        if score < min_score:
            continue
        row = row_map.get(rowid)
        if row is None:
            continue
        _, video_id, ts, caption, thumb_path, transcript = row
        source = "hybrid" if len(hit_lists) >= 2 else "fts" if hit_lists[0] is fts_hits else "clip"
        hits.append(
            VisualSearchHit(
                video_id=video_id,
                timestamp_s=float(ts),
                score=float(score),
                source=source,  # type: ignore[arg-type]
                caption=caption,
                transcript_concurrent=transcript or "",
                thumb_path=thumb_path,
                deep_link=_build_deep_link(video_id, float(ts)),
            )
        )
    return hits
