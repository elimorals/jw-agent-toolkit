"""Fakes for tests: deterministic providers and a fake chunker."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from jw_rag.chunkers.paragraph_chunker import Chunk


@dataclass
class FakeChunkerProvider:
    """Returns a canned list of actions. No-op if empty."""

    actions: list[dict[str, Any]] = field(default_factory=list)
    call_log: list[dict[str, Any]] = field(default_factory=list)

    @property
    def provider_id(self) -> str:
        return "fake"

    def propose_actions(
        self,
        *,
        source_id: str,
        chunks: list[Chunk],
        language: str,
    ) -> list[dict[str, Any]]:
        self.call_log.append(
            {"source_id": source_id, "n_chunks": len(chunks), "language": language}
        )
        return list(self.actions)


@dataclass
class FakeSemanticChunker:
    """A deterministic chunker for tests of upstream callers."""

    name: str = "semantic"

    def chunk(
        self,
        paragraphs: list[str],
        source_id: str,
        *,
        metadata: dict[str, Any] | None = None,
    ) -> list[Chunk]:
        base = dict(metadata or {})
        out: list[Chunk] = []
        for i, p in enumerate(paragraphs):
            out.append(
                Chunk(
                    id=f"{source_id}#{i}",
                    text=p.strip(),
                    source_id=source_id,
                    metadata={**base, "chunker": "semantic", "para_ids": [i]},
                )
            )
        return out
