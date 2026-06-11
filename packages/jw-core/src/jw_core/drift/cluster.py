"""Era partitioning + DBSCAN-style clustering (Fase 72).

A `Chunk` is a `(text, year, embedding)` tuple. The chunks are first
partitioned per era (decade), then each era's embeddings are clustered
with a minimal DBSCAN-style algorithm so we can compare cluster
centroids across eras.

We implement DBSCAN with cosine distance directly in numpy to avoid a
hard dependency on scikit-learn. The semantics matter: epsilon is on
cosine distance (1 - cosine_similarity), not euclidean.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from jw_core.drift.models import Era, year_to_era


@dataclass(frozen=True)
class Chunk:
    text: str
    year: int
    embedding: np.ndarray  # (dim,) float32, normalized


@dataclass(frozen=True)
class ClusterResult:
    """Result of clustering one era's chunks.

    `labels` is a list aligned with the input chunk order:
      - -1 = noise (unassigned)
      - 0, 1, 2, ... = cluster id

    `cluster_centers` maps cluster_id -> centroid vector.
    """

    labels: list[int]
    cluster_centers: dict[int, np.ndarray]


def partition_by_era(chunks: list[Chunk]) -> dict[Era, list[Chunk]]:
    """Group `chunks` by `(year // 10) * 10` -> Era."""

    by_era: dict[Era, list[Chunk]] = {}
    for c in chunks:
        era = year_to_era(c.year)
        if era is None:
            continue
        by_era.setdefault(era, []).append(c)
    return by_era


def _cosine_distance(a: np.ndarray, b: np.ndarray) -> float:
    an = float(np.linalg.norm(a))
    bn = float(np.linalg.norm(b))
    if an == 0 or bn == 0:
        return 1.0
    sim = float(np.dot(a, b) / (an * bn))
    sim = max(-1.0, min(1.0, sim))
    return 1.0 - sim


def dbscan_cluster(
    chunks: list[Chunk],
    *,
    epsilon: float = 0.30,
    min_samples: int = 2,
) -> ClusterResult:
    """Tiny DBSCAN over cosine distance.

    Returns labels in the original chunk order plus centroid vectors per
    cluster id. With fewer than `min_samples` chunks, all are noise.
    """

    n = len(chunks)
    labels = [-1] * n
    if n == 0:
        return ClusterResult(labels=labels, cluster_centers={})
    if n < min_samples:
        return ClusterResult(labels=labels, cluster_centers={})

    embeddings = np.vstack(
        [c.embedding.astype(np.float32) for c in chunks]
    )

    def _neighbors(i: int) -> list[int]:
        nbrs: list[int] = []
        for j in range(n):
            if j == i:
                continue
            if _cosine_distance(embeddings[i], embeddings[j]) <= epsilon:
                nbrs.append(j)
        return nbrs

    cluster_id = 0
    for i in range(n):
        if labels[i] != -1:
            continue
        nbrs = _neighbors(i)
        if len(nbrs) + 1 < min_samples:
            # Stays as noise for now. May still be reached as a border point.
            continue
        labels[i] = cluster_id
        seeds = list(nbrs)
        while seeds:
            j = seeds.pop()
            if labels[j] == -1:
                labels[j] = cluster_id
            elif labels[j] != cluster_id:
                continue
            else:
                continue
            sub_nbrs = _neighbors(j)
            if len(sub_nbrs) + 1 >= min_samples:
                for k in sub_nbrs:
                    if labels[k] == -1:
                        seeds.append(k)
        cluster_id += 1

    centers: dict[int, np.ndarray] = {}
    for cid in range(cluster_id):
        members = [
            embeddings[i] for i, lab in enumerate(labels) if lab == cid
        ]
        if not members:
            continue
        centroid = np.mean(np.vstack(members), axis=0)
        norm = float(np.linalg.norm(centroid))
        if norm > 0:
            centroid = centroid / norm
        centers[cid] = centroid.astype(np.float32)

    return ClusterResult(labels=labels, cluster_centers=centers)
