"""Public API for chunkers.

    from jw_rag.chunkers import get_chunker, Chunk, Chunker, ParagraphChunker
"""

from __future__ import annotations

import os
from typing import Any

from jw_rag.chunkers.paragraph_chunker import (
    Chunk,
    ParagraphChunker,
    chunk_paragraphs,
)
from jw_rag.chunkers.protocol import Chunker

__all__ = [
    "Chunk",
    "Chunker",
    "ParagraphChunker",
    "chunk_paragraphs",
    "get_chunker",
]


def get_chunker(name: str | None = None, **kwargs: Any) -> Chunker:
    """Resolve a chunker by name, env var, or default.

    Precedence: argument > $JW_CHUNKER > "paragraph".
    """

    resolved = name or os.environ.get("JW_CHUNKER", "paragraph")
    if resolved == "paragraph":
        return ParagraphChunker(**kwargs)
    if resolved == "semantic":
        from jw_rag.chunkers.semantic_chunker import SemanticChunker

        return SemanticChunker(**kwargs)
    if resolved == "llm":
        from jw_rag.chunkers.llm_chunker import LLMChunker

        return LLMChunker(**kwargs)
    raise ValueError(f"Unknown chunker: {resolved!r}")
