"""Stamp citations with the four conventional provenance keys."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from jw_agents.base import Citation, Finding
from jw_core.provenance.hashing import content_sha256


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def stamp_citation(
    citation: Citation,
    *,
    text: str,
    published_date: str | None = None,
    revision: str | None = None,
) -> Citation:
    """Write the four provenance keys into `citation.metadata` in place.

    Always written: `content_hash`, `accessed_at`.
    Written only when not None: `published_date`, `revision`.
    Returns the same citation for fluent chaining.
    """

    meta: dict[str, Any] = citation.metadata
    meta["content_hash"] = content_sha256(text)
    meta["accessed_at"] = _utcnow_iso()
    if published_date is not None:
        meta["published_date"] = published_date
    if revision is not None:
        meta["revision"] = revision
    return citation


def stamp_finding_text(
    finding: Finding,
    *,
    text: str | None = None,
    published_date: str | None = None,
    revision: str | None = None,
) -> Finding:
    """Stamp the finding's citation using `finding.excerpt` by default.

    No-op when `finding.excerpt` is empty AND no explicit `text` is given.
    """

    effective = text if text is not None else (finding.excerpt or "")
    if not effective:
        return finding
    stamp_citation(
        finding.citation,
        text=effective,
        published_date=published_date,
        revision=revision,
    )
    return finding
