"""Era partitioning + DBSCAN clustering tests (Fase 72)."""

from __future__ import annotations

import numpy as np

from jw_core.drift.cluster import (
    Chunk,
    dbscan_cluster,
    partition_by_era,
)


def _norm(v: np.ndarray) -> np.ndarray:
    n = float(np.linalg.norm(v))
    return v if n == 0 else (v / n).astype(np.float32)


def _chunk(text: str, year: int, vec: list[float]) -> Chunk:
    return Chunk(text=text, year=year, embedding=_norm(np.array(vec, dtype=np.float32)))


def test_partition_by_era_groups_correctly() -> None:
    chunks = [
        _chunk("a", 1985, [1, 0, 0]),
        _chunk("b", 1989, [0, 1, 0]),
        _chunk("c", 2024, [0, 0, 1]),
    ]
    out = partition_by_era(chunks)
    assert set(out.keys()) == {"1980s", "2020s"}
    assert len(out["1980s"]) == 2
    assert len(out["2020s"]) == 1


def test_partition_drops_out_of_range_year() -> None:
    chunks = [
        _chunk("a", 1899, [1, 0, 0]),
        _chunk("b", 2030, [0, 1, 0]),
        _chunk("c", 1985, [0, 0, 1]),
    ]
    out = partition_by_era(chunks)
    assert set(out.keys()) == {"1980s"}


def test_dbscan_clusters_close_embeddings_together() -> None:
    """Two clusters: vectors near [1,0] and vectors near [0,1]."""
    chunks = [
        _chunk("a", 1985, [1.0, 0.05, 0.0]),
        _chunk("b", 1986, [0.95, 0.10, 0.0]),
        _chunk("c", 1987, [1.0, 0.0, 0.05]),
        _chunk("d", 1985, [0.0, 1.0, 0.05]),
        _chunk("e", 1986, [0.05, 0.95, 0.0]),
        _chunk("f", 1987, [0.0, 1.0, 0.0]),
    ]
    result = dbscan_cluster(chunks, epsilon=0.30, min_samples=2)
    # All 6 should belong to some cluster (no noise)
    assert all(lab >= 0 for lab in result.labels)
    # Should produce exactly 2 cluster centers
    assert len(result.cluster_centers) == 2


def test_dbscan_returns_all_noise_when_below_min_samples() -> None:
    chunks = [_chunk("a", 1985, [1, 0, 0])]
    result = dbscan_cluster(chunks, epsilon=0.30, min_samples=2)
    assert result.labels == [-1]
    assert result.cluster_centers == {}


def test_dbscan_empty_input() -> None:
    result = dbscan_cluster([], epsilon=0.3, min_samples=2)
    assert result.labels == []
    assert result.cluster_centers == {}


def test_dbscan_centers_are_unit_normalized() -> None:
    chunks = [
        _chunk("a", 1985, [1.0, 0.0, 0.0]),
        _chunk("b", 1985, [0.99, 0.01, 0.0]),
        _chunk("c", 1985, [1.0, 0.02, 0.0]),
    ]
    result = dbscan_cluster(chunks, epsilon=0.30, min_samples=2)
    for _, center in result.cluster_centers.items():
        norm = float(np.linalg.norm(center))
        assert abs(norm - 1.0) < 1e-4
