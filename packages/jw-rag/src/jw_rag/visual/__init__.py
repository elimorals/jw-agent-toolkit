"""Visual late-interaction RAG store.

Public API will be expanded incrementally as each task lands. At the end of
Fase 37 this module re-exports the full surface (see Task 9). Until then it
keeps the minimum set so each task's tests can import without ImportError.

Heavy providers (`colpali-engine`, `transformers`, `torch`, `mlx`, `pdf2image`,
`playwright`) are imported lazily inside the provider classes. Importing this
module is safe on machines without any of them.
"""

from jw_rag.visual.errors import ConfigError, VisualStoreMismatchError

__all__ = [
    "ConfigError",
    "VisualStoreMismatchError",
]
