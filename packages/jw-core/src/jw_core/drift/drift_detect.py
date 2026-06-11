"""Drift event detection: cluster alignment + cosine delta + significance (Fase 72)."""

from __future__ import annotations

import numpy as np

from jw_core.drift.cluster import Chunk, ClusterResult
from jw_core.drift.models import (
    ALL_ERAS,
    Citation,
    DriftEvent,
    Era,
    EraSnapshot,
    Significance,
)


def _representative_indices(
    labels: list[int], cluster_id: int, *, max_n: int = 3
) -> list[int]:
    """Return the first `max_n` chunk indices that belong to the cluster."""
    return [i for i, lab in enumerate(labels) if lab == cluster_id][:max_n]


def build_era_snapshot(
    *,
    era: Era,
    chunks: list[Chunk],
    cluster: ClusterResult,
) -> EraSnapshot:
    """Build an `EraSnapshot` from chunks + cluster result.

    Picks the largest cluster as the canonical center; the snapshot
    records representative chunks/citations for human inspection.
    """

    if not chunks:
        return EraSnapshot(era=era, chunk_count=0)

    # Pick the most populated cluster as the canonical centroid.
    if cluster.cluster_centers:
        size_by_cid = {
            cid: cluster.labels.count(cid)
            for cid in cluster.cluster_centers
        }
        canonical_cid = max(size_by_cid.items(), key=lambda kv: kv[1])[0]
        rep_indices = _representative_indices(
            cluster.labels, canonical_cid, max_n=3
        )
    else:
        canonical_cid = -1
        rep_indices = list(range(min(3, len(chunks))))

    rep_chunks = [chunks[i].text for i in rep_indices]
    rep_citations = [
        Citation(
            text=chunks[i].text[:200],
            pub_code="",
            year=chunks[i].year,
        )
        for i in rep_indices
    ]

    return EraSnapshot(
        era=era,
        chunk_count=len(chunks),
        representative_chunks=rep_chunks,
        representative_citations=rep_citations,
        cluster_count=len(cluster.cluster_centers),
        cluster_center_embedding_id=canonical_cid,
    )


def _center_of(
    era: Era,
    *,
    chunks: list[Chunk],
    cluster: ClusterResult,
) -> np.ndarray | None:
    """Return the canonical centroid vector for an era, or None."""
    if not cluster.cluster_centers:
        if not chunks:
            return None
        v = np.mean(
            np.vstack([c.embedding for c in chunks]), axis=0
        )
        norm = float(np.linalg.norm(v))
        if norm > 0:
            v = v / norm
        return v.astype(np.float32)
    sizes = {
        cid: cluster.labels.count(cid)
        for cid in cluster.cluster_centers
    }
    canonical_cid = max(sizes.items(), key=lambda kv: kv[1])[0]
    return cluster.cluster_centers[canonical_cid]


def classify_significance(
    cosine_delta: float, *, chunk_counts: tuple[int, int]
) -> Significance:
    a, b = chunk_counts
    if min(a, b) < 5:
        return "minor"
    if cosine_delta < 0.05:
        return "minor"
    if cosine_delta < 0.15:
        return "moderate"
    return "major"


def detect_drift_events(
    *,
    era_chunks: dict[Era, list[Chunk]],
    era_clusters: dict[Era, ClusterResult],
    min_delta: float = 0.01,
) -> list[DriftEvent]:
    """Build a `DriftEvent` between consecutive eras with enough data."""

    # Use canonical era order
    populated = [
        era for era in ALL_ERAS if era in era_chunks and era_chunks[era]
    ]
    if len(populated) < 2:
        return []

    events: list[DriftEvent] = []
    for from_era, to_era in zip(populated[:-1], populated[1:], strict=False):
        from_center = _center_of(
            from_era,
            chunks=era_chunks[from_era],
            cluster=era_clusters.get(
                from_era, ClusterResult(labels=[], cluster_centers={})
            ),
        )
        to_center = _center_of(
            to_era,
            chunks=era_chunks[to_era],
            cluster=era_clusters.get(
                to_era, ClusterResult(labels=[], cluster_centers={})
            ),
        )
        if from_center is None or to_center is None:
            continue
        sim = float(np.dot(from_center, to_center))
        sim = max(-1.0, min(1.0, sim))
        delta = max(0.0, 1.0 - sim)
        if delta < min_delta:
            continue
        sig = classify_significance(
            delta,
            chunk_counts=(
                len(era_chunks[from_era]),
                len(era_chunks[to_era]),
            ),
        )
        from_chunk = era_chunks[from_era][0]
        to_chunk = era_chunks[to_era][0]
        events.append(
            DriftEvent(
                from_era=from_era,
                to_era=to_era,
                cosine_delta=delta,
                significance=sig,
                summary_change=(
                    f"Cluster center shift from {from_era} to {to_era} "
                    f"(delta={delta:.3f})."
                ),
                from_citation=Citation(
                    text=from_chunk.text[:200],
                    pub_code="",
                    year=from_chunk.year,
                ),
                to_citation=Citation(
                    text=to_chunk.text[:200],
                    pub_code="",
                    year=to_chunk.year,
                ),
            )
        )
    return events
