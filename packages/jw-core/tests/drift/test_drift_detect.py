"""Drift event detection tests (Fase 72)."""

from __future__ import annotations

import numpy as np

from jw_core.drift.cluster import (
    Chunk,
    ClusterResult,
    dbscan_cluster,
    partition_by_era,
)
from jw_core.drift.drift_detect import (
    build_era_snapshot,
    classify_significance,
    detect_drift_events,
)


def _norm(v: list[float]) -> np.ndarray:
    arr = np.array(v, dtype=np.float32)
    n = float(np.linalg.norm(arr))
    return arr if n == 0 else (arr / n).astype(np.float32)


def _chunk(text: str, year: int, vec: list[float]) -> Chunk:
    return Chunk(text=text, year=year, embedding=_norm(vec))


def test_classify_significance_minor_when_small_sample() -> None:
    assert classify_significance(0.5, chunk_counts=(2, 3)) == "minor"


def test_classify_significance_major_when_large_delta() -> None:
    assert classify_significance(0.30, chunk_counts=(10, 10)) == "major"


def test_classify_significance_moderate_in_band() -> None:
    assert classify_significance(0.10, chunk_counts=(10, 10)) == "moderate"


def test_build_era_snapshot_uses_largest_cluster() -> None:
    chunks = [
        _chunk("a", 1985, [1.0, 0.0]),
        _chunk("b", 1986, [0.99, 0.01]),
        _chunk("c", 1987, [0.0, 1.0]),
    ]
    cluster = dbscan_cluster(chunks, epsilon=0.20, min_samples=2)
    snap = build_era_snapshot(
        era="1980s", chunks=chunks, cluster=cluster
    )
    assert snap.era == "1980s"
    assert snap.chunk_count == 3
    # The (1,0) cluster has 2 members so it's canonical
    assert snap.representative_chunks


def test_detect_drift_events_yields_event_when_centers_shift() -> None:
    chunks = [
        _chunk("a", 1985, [1.0, 0.05]),
        _chunk("b", 1986, [0.95, 0.10]),
        _chunk("c", 2024, [0.0, 1.0]),
        _chunk("d", 2025, [0.05, 0.95]),
    ]
    era_chunks = partition_by_era(chunks)
    era_clusters = {
        era: dbscan_cluster(cs, epsilon=0.30, min_samples=2)
        for era, cs in era_chunks.items()
    }
    events = detect_drift_events(
        era_chunks=era_chunks, era_clusters=era_clusters
    )
    assert events
    e = events[0]
    assert e.from_era == "1980s"
    assert e.to_era == "2020s"
    assert e.cosine_delta > 0.5


def test_detect_drift_events_empty_when_one_era() -> None:
    chunks = [
        _chunk("a", 1985, [1.0, 0.0]),
        _chunk("b", 1986, [0.99, 0.01]),
    ]
    era_chunks = partition_by_era(chunks)
    era_clusters = {
        era: ClusterResult(labels=[-1] * len(cs), cluster_centers={})
        for era, cs in era_chunks.items()
    }
    events = detect_drift_events(
        era_chunks=era_chunks, era_clusters=era_clusters
    )
    assert events == []


def test_detect_drift_events_skips_tiny_delta() -> None:
    chunks = [
        _chunk("a", 1985, [1.0, 0.0]),
        _chunk("b", 1986, [1.0, 0.0]),
        _chunk("c", 2024, [1.0, 0.0]),
        _chunk("d", 2025, [1.0, 0.0]),
    ]
    era_chunks = partition_by_era(chunks)
    era_clusters = {
        era: dbscan_cluster(cs, epsilon=0.30, min_samples=2)
        for era, cs in era_chunks.items()
    }
    events = detect_drift_events(
        era_chunks=era_chunks, era_clusters=era_clusters, min_delta=0.05
    )
    assert events == []
