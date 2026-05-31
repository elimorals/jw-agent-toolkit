"""Public re-exports for the rerank stack.

Mirror of `jw_rag.embed` (which holds the `Embedder` Protocol + FakeEmbedder)
but for the rerank side. The full Protocol lives in `rerank_providers.factory`
so the factory can use it without circular imports.
"""

from __future__ import annotations

from jw_rag.rerank_providers import (
    Reranker,
    Target,
    get_default_reranker,
    list_available_rerankers,
)

__all__ = ["Reranker", "Target", "get_default_reranker", "list_available_rerankers"]
