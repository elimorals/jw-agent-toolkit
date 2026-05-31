"""Multi-vector store with MaxSim scoring.

NOT a subclass of `jw_rag.store.VectorStore`. The interfaces are similar
(`add`, `search`, `save`, `load`, `is_empty`, `source_ids`) but the internal
representation is multi-vector: each document is a `(max_patches, dim)`
matrix plus a `(max_patches,)` boolean mask.

Persistence layout under `path`:
    meta.json     — {model_name, dim, max_patches, count, ...}
    chunks.jsonl  — one VisualChunk per line
    vectors.npy   — (N, max_patches, dim) float16, zero-padded
    mask.npy      — (N, max_patches) bool

MaxSim:
    score(q, d) = Σ_qtok max_dpatch <q_tok, d_patch>     (mask out padding)

For top-k retrieval over N docs we compute the full (N, max_patches) sim
tensor once per q_token using a batched matmul. That's O(N · max_patches ·
dim · |q|); fine up to ~10k pages in CPU/numpy and far better in GPU
(future v2 can add PLAID ANN if needed).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

from jw_rag.visual.errors import VisualStoreMismatchError
from jw_rag.visual.models import MultiVectorHit, VisualChunk


class _EmbedderProtocol:
    """Structural type for any ColPali-like embedder."""

    name: str
    dim: int
    max_patches: int

    def embed_image(self, image: Image.Image) -> np.ndarray: ...
    def embed_query(self, query: str) -> np.ndarray: ...


class VisualVectorStore:
    """Multi-vector store + MaxSim search + JSON/npy persistence."""

    def __init__(self, path: Path | str, embedder: _EmbedderProtocol) -> None:
        self.path = Path(path)
        self.embedder = embedder
        self._chunks: list[VisualChunk] = []
        self._vectors: np.ndarray = np.zeros((0, embedder.max_patches, embedder.dim), dtype=np.float16)
        self._mask: np.ndarray = np.zeros((0, embedder.max_patches), dtype=bool)
        self._known_ids: set[str] = set()

    # ── State ───────────────────────────────────────────────────────────

    @property
    def count(self) -> int:
        return len(self._chunks)

    @property
    def is_empty(self) -> bool:
        return self.count == 0

    def source_ids(self) -> set[str]:
        return {c.source_id for c in self._chunks if c.source_id}

    # ── Index ───────────────────────────────────────────────────────────

    def add(self, pairs: list[tuple[VisualChunk, Image.Image]]) -> None:
        """Embed and append each (chunk, image). Skips chunks already present."""
        if not pairs:
            return
        max_p = self.embedder.max_patches
        dim = self.embedder.dim
        new_vecs: list[np.ndarray] = []
        new_masks: list[np.ndarray] = []
        new_chunks: list[VisualChunk] = []
        for chunk, image in pairs:
            if chunk.id in self._known_ids:
                continue
            patches = self.embedder.embed_image(image)
            n = patches.shape[0]
            if n > max_p:
                patches = patches[:max_p]
                n = max_p
            padded = np.zeros((max_p, dim), dtype=np.float16)
            padded[:n] = patches
            mask = np.zeros((max_p,), dtype=bool)
            mask[:n] = True
            new_vecs.append(padded)
            new_masks.append(mask)
            new_chunks.append(chunk)
            self._known_ids.add(chunk.id)
        if not new_chunks:
            return
        block_v = np.stack(new_vecs, axis=0)
        block_m = np.stack(new_masks, axis=0)
        if self.count == 0:
            self._vectors = block_v
            self._mask = block_m
        else:
            self._vectors = np.concatenate([self._vectors, block_v], axis=0)
            self._mask = np.concatenate([self._mask, block_m], axis=0)
        self._chunks.extend(new_chunks)

    # ── Search ──────────────────────────────────────────────────────────

    def search(self, query: str, top_k: int = 10) -> list[MultiVectorHit]:
        if self.is_empty:
            return []
        q_vecs = self.embedder.embed_query(query).astype(np.float32)  # (Q, D)
        d_vecs = self._vectors.astype(np.float32)  # (N, P, D)
        d_mask = self._mask  # (N, P)

        # sims: (N, Q, P) via einsum.
        sims = np.einsum("npd,qd->nqp", d_vecs, q_vecs)
        # Mask invalid patches with -inf so they never win the max.
        mask_broadcast = d_mask[:, np.newaxis, :]  # (N, 1, P)
        sims = np.where(mask_broadcast, sims, -np.inf)
        per_token_max = sims.max(axis=2)  # (N, Q)
        scores = per_token_max.sum(axis=1)  # (N,)

        top_k = min(top_k, self.count)
        idx = np.argpartition(-scores, top_k - 1)[:top_k]
        idx = idx[np.argsort(-scores[idx])]
        return [
            MultiVectorHit(chunk=self._chunks[i], score=float(scores[i]), rank=r, source="visual")
            for r, i in enumerate(idx, 1)
        ]

    # ── Persistence ─────────────────────────────────────────────────────

    def save(self) -> None:
        self.path.mkdir(parents=True, exist_ok=True)
        with (self.path / "chunks.jsonl").open("w", encoding="utf-8") as f:
            for c in self._chunks:
                f.write(json.dumps(c.to_dict(), ensure_ascii=False) + "\n")
        np.save(self.path / "vectors.npy", self._vectors)
        np.save(self.path / "mask.npy", self._mask)
        (self.path / "meta.json").write_text(
            json.dumps(
                {
                    "multi_vector": True,
                    "model_name": getattr(self.embedder, "name", "unknown"),
                    "dim": int(self.embedder.dim),
                    "max_patches": int(self.embedder.max_patches),
                    "count": self.count,
                }
            )
        )

    def load(self) -> None:
        meta_path = self.path / "meta.json"
        if not meta_path.exists():
            return
        meta: dict[str, Any] = json.loads(meta_path.read_text(encoding="utf-8"))
        if meta.get("dim") != int(self.embedder.dim):
            raise VisualStoreMismatchError(
                f"dim mismatch: store={meta.get('dim')} embedder={self.embedder.dim}. "
                "Re-ingest with `jw rag ingest-visual --force`."
            )
        if meta.get("max_patches") != int(self.embedder.max_patches):
            raise VisualStoreMismatchError(
                f"max_patches mismatch: store={meta.get('max_patches')} "
                f"embedder={self.embedder.max_patches}. Re-ingest."
            )
        if meta.get("model_name") and meta["model_name"] != getattr(self.embedder, "name", ""):
            # Soft warn via exception: only raise if name differs AND user wants to read.
            # We raise to be safe — silent acceptance breaks the cache invariant.
            raise VisualStoreMismatchError(
                f"model mismatch: store={meta['model_name']} embedder={self.embedder.name}. "
                "Re-ingest."
            )
        self._chunks = []
        with (self.path / "chunks.jsonl").open("r", encoding="utf-8") as f:
            for line in f:
                self._chunks.append(VisualChunk.from_dict(json.loads(line)))
        self._vectors = np.load(self.path / "vectors.npy")
        self._mask = np.load(self.path / "mask.npy")
        self._known_ids = {c.id for c in self._chunks}
