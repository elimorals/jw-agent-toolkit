"""Hybrid retrieval store: vectors (numpy) + BM25 (rank_bm25) + JSON persistence.

This is intentionally simple — designed for tens of thousands of chunks, not
millions. For larger corpora plug in a real vector DB (sqlite-vec, Qdrant,
Pinecone) via the Embedder protocol + a future `Store` protocol.

Persistence layout under `path`:
    chunks.jsonl   — one JSON object per chunk
    vectors.npy    — (N, dim) float32 matrix
    meta.json      — embedder dim + count
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from rank_bm25 import BM25Okapi

from jw_rag.chunker import Chunk
from jw_rag.embed import Embedder, l2_normalize


@dataclass
class SearchHit:
    chunk: Chunk
    score: float
    rank: int
    source: str  # "vector", "bm25", or "hybrid"


class VectorStore:
    """In-memory hybrid store with JSON-on-disk persistence."""

    def __init__(self, path: Path | str, embedder: Embedder) -> None:
        self.path = Path(path)
        self.embedder = embedder
        self._chunks: list[Chunk] = []
        self._vectors: np.ndarray = np.zeros((0, embedder.dim), dtype=np.float32)
        self._bm25: BM25Okapi | None = None
        self._tokenized: list[list[str]] = []

    # ── State ──────────────────────────────────────────────────────────

    @property
    def count(self) -> int:
        return len(self._chunks)

    @property
    def is_empty(self) -> bool:
        return self.count == 0

    # ── Index ──────────────────────────────────────────────────────────

    def add(self, chunks: list[Chunk]) -> None:
        """Add chunks to the store. Re-embeds and rebuilds BM25."""
        if not chunks:
            return
        texts = [c.text for c in chunks]
        new_vecs = l2_normalize(self.embedder.embed(texts))
        self._chunks.extend(chunks)
        self._vectors = np.vstack([self._vectors, new_vecs]) if self.count > len(chunks) else new_vecs
        # Rebuild BM25 (rank_bm25 doesn't support incremental updates).
        self._tokenized = [_tokenize(c.text) for c in self._chunks]
        self._bm25 = BM25Okapi(self._tokenized) if self._tokenized else None

    def delete_by_source_ids(self, source_ids: list[str]) -> int:
        """Remove every chunk whose `source_id` is in `source_ids`.

        Returns the number of chunks removed. Re-indexes vectors and BM25
        afterwards if anything changed. No-op when `source_ids` is empty.
        Used by the incremental sync pipeline to evict notes the user
        deleted or modified.
        """
        if not source_ids:
            return 0
        targets = set(source_ids)
        keep_mask = [c.source_id not in targets for c in self._chunks]
        removed = self.count - sum(keep_mask)
        if removed == 0:
            return 0
        self._chunks = [c for c, keep in zip(self._chunks, keep_mask) if keep]
        if self._vectors.size:
            self._vectors = self._vectors[np.array(keep_mask, dtype=bool)]
        self._tokenized = [_tokenize(c.text) for c in self._chunks]
        self._bm25 = BM25Okapi(self._tokenized) if self._tokenized else None
        return removed

    def source_ids(self) -> set[str]:
        """Return the unique `source_id` values currently indexed."""
        return {c.source_id for c in self._chunks if c.source_id}

    def has_source(self, source_id: str) -> bool:
        """True if at least one chunk in the store carries this `source_id`.

        Used by loaders (F62) to skip re-ingesting a file whose
        content-hash matches an existing source — gives idempotency
        without scanning the entire chunk list at call sites.
        """
        return any(c.source_id == source_id for c in self._chunks)

    def list_chunks(self) -> list[Chunk]:
        """Shallow copy of every chunk currently indexed.

        Read-only helper for tests and small ad-hoc scripts. Don't use
        on production-size stores — for those rely on the search APIs.
        """
        return list(self._chunks)

    # ── Search ─────────────────────────────────────────────────────────

    def vector_search(self, query: str, top_k: int = 10) -> list[SearchHit]:
        """Cosine-similarity search via dot product of L2-normalized vectors."""
        if self.is_empty:
            return []
        qvec = l2_normalize(self.embedder.embed([query]))[0]
        sims = self._vectors @ qvec
        top_k = min(top_k, len(sims))
        idx = np.argpartition(-sims, top_k - 1)[:top_k]
        idx = idx[np.argsort(-sims[idx])]
        return [
            SearchHit(chunk=self._chunks[i], score=float(sims[i]), rank=r, source="vector")
            for r, i in enumerate(idx, 1)
        ]

    def bm25_search(self, query: str, top_k: int = 10) -> list[SearchHit]:
        """BM25 keyword search."""
        if self.is_empty or self._bm25 is None:
            return []
        scores = self._bm25.get_scores(_tokenize(query))
        top_k = min(top_k, len(scores))
        idx = np.argpartition(-scores, top_k - 1)[:top_k]
        idx = idx[np.argsort(-scores[idx])]
        return [
            SearchHit(chunk=self._chunks[i], score=float(scores[i]), rank=r, source="bm25")
            for r, i in enumerate(idx, 1)
        ]

    def hybrid_search(
        self,
        query: str,
        top_k: int = 10,
        *,
        candidate_pool: int = 50,
        rrf_k: int = 60,
        rerank: bool = True,
        reranker: object | None = None,  # Reranker — typed as object to avoid import cycle
    ) -> list[SearchHit]:
        """Reciprocal Rank Fusion across BM25 and vector results, then optional rerank.

        Backwards compat: with `rerank=False`, output is bit-identical to the
        pre-Fase-33 behavior. With `rerank=True` and no real reranker
        available, the factory returns NoOpReranker (passthrough) so the order
        stays the same but `source` becomes "hybrid+rerank" — this is the only
        observable change for offline callers.
        """
        vec_hits = self.vector_search(query, top_k=candidate_pool)
        bm25_hits = self.bm25_search(query, top_k=candidate_pool)
        fused: dict[str, tuple[float, Chunk]] = {}
        for hits in (vec_hits, bm25_hits):
            for hit in hits:
                contribution = 1.0 / (rrf_k + hit.rank)
                if hit.chunk.id in fused:
                    prev_score, _ = fused[hit.chunk.id]
                    fused[hit.chunk.id] = (prev_score + contribution, hit.chunk)
                else:
                    fused[hit.chunk.id] = (contribution, hit.chunk)

        ordered = sorted(fused.values(), key=lambda t: -t[0])
        if not ordered:
            return []

        if not rerank:
            return [
                SearchHit(chunk=c, score=float(s), rank=r, source="hybrid")
                for r, (s, c) in enumerate(ordered[:top_k], 1)
            ]

        # Resolve reranker lazily to avoid touching factory on cold paths.
        if reranker is None:
            from jw_rag.rerank_providers.factory import get_default_reranker

            reranker = get_default_reranker()

        texts = [c.text for _, c in ordered]
        scores = reranker.rerank(query, texts)  # type: ignore[union-attr]
        reranked = sorted(zip(scores, ordered, strict=True), key=lambda t: -t[0])

        return [
            SearchHit(chunk=c, score=float(s), rank=r, source="hybrid+rerank")
            for r, (s, (_, c)) in enumerate(reranked[:top_k], 1)
        ]

    # ── Persistence ────────────────────────────────────────────────────

    def save(self) -> None:
        self.path.mkdir(parents=True, exist_ok=True)
        with (self.path / "chunks.jsonl").open("w", encoding="utf-8") as f:
            for c in self._chunks:
                f.write(
                    json.dumps(
                        {
                            "id": c.id,
                            "text": c.text,
                            "source_id": c.source_id,
                            "metadata": c.metadata,
                        },
                        ensure_ascii=False,
                    )
                    + "\n"
                )
        np.save(self.path / "vectors.npy", self._vectors)
        (self.path / "meta.json").write_text(
            json.dumps(
                {
                    "dim": self.embedder.dim,
                    "count": self.count,
                }
            )
        )

    def load(self) -> None:
        if not (self.path / "meta.json").exists():
            return
        meta = json.loads((self.path / "meta.json").read_text())
        if meta["dim"] != self.embedder.dim:
            raise ValueError(f"Embedder dim mismatch: stored={meta['dim']} embedder={self.embedder.dim}")
        self._chunks = []
        with (self.path / "chunks.jsonl").open("r", encoding="utf-8") as f:
            for line in f:
                data = json.loads(line)
                self._chunks.append(
                    Chunk(
                        id=data["id"],
                        text=data["text"],
                        source_id=data.get("source_id", ""),
                        metadata=data.get("metadata", {}),
                    )
                )
        self._vectors = np.load(self.path / "vectors.npy")
        self._tokenized = [_tokenize(c.text) for c in self._chunks]
        self._bm25 = BM25Okapi(self._tokenized) if self._tokenized else None


# ── Tokenizer ──────────────────────────────────────────────────────────


def _tokenize(text: str) -> list[str]:
    """Lowercase + whitespace + strip punctuation. Naive but works for BM25."""
    import re

    return [t for t in re.findall(r"\w+", text.lower()) if len(t) > 1]
