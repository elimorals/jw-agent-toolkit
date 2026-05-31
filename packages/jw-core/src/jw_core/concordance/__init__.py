"""Exact-match concordance over the local decrypted JW corpus.

Public API:
    from jw_core.concordance import (
        build_index,
        concordance_search,
        ConcordanceHit,
        IndexEntry,
        ConcordanceStore,
        default_db_path,
    )

See `docs/superpowers/specs/2026-05-30-fase-28-concordance-design.md`.
"""

from jw_core.concordance.indexer import NWTChapter, build_index
from jw_core.concordance.models import ConcordanceHit, IndexEntry
from jw_core.concordance.search import concordance_search, escape_fts_phrase
from jw_core.concordance.store import ConcordanceStore, default_db_path

__all__ = [
    "ConcordanceHit",
    "ConcordanceStore",
    "IndexEntry",
    "NWTChapter",
    "build_index",
    "concordance_search",
    "default_db_path",
    "escape_fts_phrase",
]
