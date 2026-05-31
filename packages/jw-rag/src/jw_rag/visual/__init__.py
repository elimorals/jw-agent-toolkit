"""Visual late-interaction RAG store.

Public API:
    from jw_rag.visual import (
        VisualChunk,
        MultiVectorHit,
        IngestResult,
        VisualVectorStore,
        ConfigError,
        VisualStoreMismatchError,
        hybrid_search_with_visual,
        get_default_visual_embedder,
        ingest_path_visual,
        FakeColPaliEmbedder,
        FakeRasterizer,
    )

Heavy providers (`colpali-engine`, `transformers`, `torch`, `mlx`, `pdf2image`,
`playwright`) are imported lazily inside the provider classes. Importing this
module is safe on machines without any of them.
"""

from jw_rag.visual.colpali import (
    ColPaliEmbedder,
    ColQwen2Embedder,
    get_default_visual_embedder,
)
from jw_rag.visual.errors import ConfigError, VisualStoreMismatchError
from jw_rag.visual.fakes import FakeColPaliEmbedder, FakeRasterizer
from jw_rag.visual.hybrid import hybrid_search_with_visual
from jw_rag.visual.ingest import (
    ingest_epub_visual,
    ingest_jwpub_visual,
    ingest_path_visual,
    ingest_pdf_visual,
)
from jw_rag.visual.models import IngestResult, MultiVectorHit, VisualChunk
from jw_rag.visual.page_rasterizer import PageRasterizer, rasterize_any
from jw_rag.visual.visual_store import VisualVectorStore

__all__ = [
    "ColPaliEmbedder",
    "ColQwen2Embedder",
    "ConfigError",
    "FakeColPaliEmbedder",
    "FakeRasterizer",
    "IngestResult",
    "MultiVectorHit",
    "PageRasterizer",
    "VisualChunk",
    "VisualStoreMismatchError",
    "VisualVectorStore",
    "get_default_visual_embedder",
    "hybrid_search_with_visual",
    "ingest_epub_visual",
    "ingest_jwpub_visual",
    "ingest_path_visual",
    "ingest_pdf_visual",
    "rasterize_any",
]
