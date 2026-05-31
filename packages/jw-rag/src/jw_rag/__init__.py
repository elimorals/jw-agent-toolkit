"""jw-rag — Vector indexing and hybrid retrieval over the JW corpus.

Public surface:
    from jw_rag import VectorStore, FakeEmbedder, Chunk, chunk_paragraphs
    from jw_rag import EmbedProvider, Reranker, get_default_embedder, get_default_reranker
"""

from jw_rag.chunker import Chunk, chunk_paragraphs
from jw_rag.embed import Embedder, FakeEmbedder
from jw_rag.embed_providers import (
    EmbedProvider,
    get_default_embedder,
    list_available_embedders,
)
from jw_rag.rerank import (
    Reranker,
    get_default_reranker,
    list_available_rerankers,
)
from jw_rag.store import SearchHit, VectorStore

__version__ = "0.1.0"

__all__ = [
    "Chunk",
    "EmbedProvider",
    "Embedder",
    "FakeEmbedder",
    "Reranker",
    "SearchHit",
    "VectorStore",
    "chunk_paragraphs",
    "get_default_embedder",
    "get_default_reranker",
    "list_available_embedders",
    "list_available_rerankers",
]
