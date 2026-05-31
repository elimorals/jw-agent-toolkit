"""Pydantic models for the concordance index."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

SourceKind = Literal["nwt", "jwpub", "epub"]


class IndexEntry(BaseModel):
    """One row inserted into `concordance_entries`.

    The pair (source_kind, source_id) identifies the document; `ref` is the
    human-readable citation anchor (e.g. "Juan 3:16" or "doc#42 p7").
    """

    source_kind: SourceKind
    source_id: str
    ref: str
    chunk_text: str
    language: str
    url: str | None = None
    source_path: str | None = None
    source_sha256: str = ""


class ConcordanceHit(BaseModel):
    """One result returned by `concordance_search`."""

    entry_id: int
    source_kind: SourceKind
    source_id: str
    ref: str
    snippet: str  # FTS5 snippet() output with ‹…› markers around the match
    language: str
    url: str | None
