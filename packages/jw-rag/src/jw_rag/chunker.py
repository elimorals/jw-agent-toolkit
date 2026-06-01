"""Legacy module — façade only.

Existing imports keep working:

    from jw_rag.chunker import Chunk, chunk_paragraphs

New code should prefer:

    from jw_rag.chunkers import get_chunker, Chunk
"""

from __future__ import annotations

from jw_rag.chunkers.paragraph_chunker import Chunk, chunk_paragraphs

__all__ = ["Chunk", "chunk_paragraphs"]
