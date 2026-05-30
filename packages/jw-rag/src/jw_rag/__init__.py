"""jw-rag — Vector indexing and hybrid retrieval over the JW corpus.

Public surface:
    from jw_rag import VectorStore, FakeEmbedder, Chunk, chunk_paragraphs
"""

from jw_rag.chunker import Chunk, chunk_paragraphs
from jw_rag.embed import Embedder, FakeEmbedder
from jw_rag.store import SearchHit, VectorStore

__version__ = "0.1.0"

__all__ = [
    "Chunk",
    "Embedder",
    "FakeEmbedder",
    "SearchHit",
    "VectorStore",
    "chunk_paragraphs",
]
