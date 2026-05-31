"""Embed providers for jw-rag.

Public surface:
    from jw_rag.embed_providers import (
        EmbedProvider, Target,
        get_default_embedder, list_available_embedders,
    )

Providers are imported lazily — touching this module does NOT import any
heavy SDK (sentence-transformers, cohere, voyageai). The factory probes
availability with `importlib.util.find_spec` + env-var presence.
"""

from __future__ import annotations

from jw_rag.embed_providers.factory import (
    EmbedProvider,
    Target,
    get_default_embedder,
    list_available_embedders,
)

__all__ = [
    "EmbedProvider",
    "Target",
    "get_default_embedder",
    "list_available_embedders",
]
