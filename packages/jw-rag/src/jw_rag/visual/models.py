"""Data models for the visual RAG subsystem.

A `VisualChunk` is one rasterized page. It mirrors `jw_rag.chunker.Chunk`
enough that agents can treat it the same (`.text`, `.metadata`, `.source_id`)
but adds page-level fields (`page_number`, `image_path`).

A `MultiVectorHit` is the visual analogue of `SearchHit`: same shape, same
`source` field convention ("visual" instead of "vector"/"bm25"/"hybrid").

An `IngestResult` aggregates per-file ingest stats; `__add__` lets callers
fold many file results into one summary.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class VisualChunk:
    """One rasterized page indexed by the visual store."""

    id: str
    source_id: str
    page_number: int
    image_path: Path
    ocr_text: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def text(self) -> str:
        """Alias so VisualChunk can be consumed wherever Chunk-like is expected."""
        return self.ocr_text

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "source_id": self.source_id,
            "page_number": self.page_number,
            "image_path": str(self.image_path),
            "ocr_text": self.ocr_text,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> VisualChunk:
        return cls(
            id=data["id"],
            source_id=data["source_id"],
            page_number=int(data["page_number"]),
            image_path=Path(data["image_path"]),
            ocr_text=data.get("ocr_text", ""),
            metadata=data.get("metadata", {}) or {},
        )


@dataclass
class MultiVectorHit:
    """Result of a visual MaxSim search.

    `score` is unbounded above (sum-of-maxes), not a similarity in [0, 1].
    Callers should treat scores as comparable only within the same query.
    """

    chunk: VisualChunk
    score: float
    rank: int
    source: str = "visual"


@dataclass
class IngestResult:
    """Aggregated counters for a visual ingest call."""

    pages_added: int = 0
    pages_skipped: int = 0
    duration_ms: int = 0

    def __add__(self, other: IngestResult) -> IngestResult:
        return IngestResult(
            pages_added=self.pages_added + other.pages_added,
            pages_skipped=self.pages_skipped + other.pages_skipped,
            duration_ms=self.duration_ms + other.duration_ms,
        )
