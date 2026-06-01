"""Chunker Protocol — PEP 544 structural typing."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from jw_rag.chunkers.paragraph_chunker import Chunk


@runtime_checkable
class Chunker(Protocol):
    name: str

    def chunk(
        self,
        paragraphs: list[str],
        source_id: str,
        *,
        metadata: dict[str, Any] | None = None,
    ) -> list[Chunk]: ...
