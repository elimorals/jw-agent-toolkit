"""Pydantic models for provenance.

`ProvenanceRecord` is a read-only typed view over the four conventional
keys that live inside `Citation.metadata`. `ProvenanceVerdict` and
`ProvenanceReport` carry the result of a re-fetch comparison and an
aggregate of those, respectively.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class ProvenanceRecord(BaseModel):
    """Typed view over the four provenance keys in `Citation.metadata`.

    Two of the four are required for the view to be meaningful:
      - `accessed_at`  — when the toolkit pulled the text
      - `content_hash` — sha256 hex of the canonicalized passage

    The other two are recommended but optional:
      - `published_date` — original publication date (ISO 8601)
      - `revision`       — translation revision tag, e.g. "rev. 2023"
    """

    model_config = ConfigDict(extra="forbid", frozen=False, str_strip_whitespace=False)

    accessed_at: str
    content_hash: str
    published_date: str | None = None
    revision: str | None = None

    @classmethod
    def from_citation_metadata(cls, meta: dict[str, Any]) -> "ProvenanceRecord | None":
        """Project a Citation.metadata dict into a typed record.

        Returns None when either anchor field is missing — backwards-compat
        path for citations emitted before Fase 40. Never mutates source.
        """

        if not isinstance(meta, dict):
            return None
        accessed_at = meta.get("accessed_at")
        content_hash = meta.get("content_hash")
        if not isinstance(accessed_at, str) or not isinstance(content_hash, str):
            return None
        if not accessed_at or not content_hash:
            return None
        published_date = meta.get("published_date")
        if published_date is not None and not isinstance(published_date, str):
            published_date = None
        revision = meta.get("revision")
        if revision is not None and not isinstance(revision, str):
            revision = None
        return cls(
            accessed_at=accessed_at,
            content_hash=content_hash,
            published_date=published_date,
            revision=revision,
        )


VerdictStatus = Literal["match", "changed", "unreachable", "no_record", "skipped"]


class ProvenanceVerdict(BaseModel):
    """The result of comparing a single citation's stored hash to a re-fetch.

    Statuses:
      - "match":       current text canonicalizes to the same hash as stored.
      - "changed":     hashes differ — the live text has been edited.
      - "unreachable": fetcher raised or returned non-2xx — verdict unknown.
      - "no_record":   the citation lacked provenance metadata (backcompat).
      - "skipped":     `check_since` excluded by date threshold.
    """

    model_config = ConfigDict(extra="forbid")

    url: str
    status: VerdictStatus
    original_hash: str | None
    current_hash: str | None
    delta_chars: int | None
    accessed_at_original: str | None
    accessed_at_recheck: str
    nli_rerun: dict[str, Any] | None = None
    notes: list[str] = Field(default_factory=list)


class ProvenanceReport(BaseModel):
    """Aggregate of many ProvenanceVerdicts produced in a single run."""

    model_config = ConfigDict(extra="forbid")

    started_at: datetime
    finished_at: datetime
    verdicts: list[ProvenanceVerdict] = Field(default_factory=list)
    summary: dict[str, int] = Field(default_factory=dict)

    @staticmethod
    def summarize(verdicts: list[ProvenanceVerdict]) -> dict[str, int]:
        """Roll up counts per status. Missing statuses yield 0 on demand."""

        counts: dict[str, int] = {}
        for v in verdicts:
            counts[v.status] = counts.get(v.status, 0) + 1
        return counts
