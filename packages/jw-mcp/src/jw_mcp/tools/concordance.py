"""MCP tool wrappers for the concordance module.

Both tools degrade gracefully: any RuntimeError / ValueError from the
underlying API is captured and returned as `{"error": "..."}` so the MCP
session survives transient failures.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from jw_core.concordance import build_index, concordance_search


def concordance_build_index_tool(
    paths: list[str],
    language: str,
    force: bool = False,
) -> dict[str, Any]:
    """Ingest .epub / .jwpub files into the concordance index.

    Args:
        paths: list of file paths (NOT directories — expand at the caller).
        language: ISO code (en/es/pt/...).
        force: re-index even if the sha256 has not changed.

    Returns:
        {"inserted": int, "files": int} on success, {"error": "..."} on failure.
    """

    try:
        file_paths = [Path(p) for p in paths]
        n = build_index(paths=file_paths, language=language, force=force)
        return {"inserted": n, "files": len(file_paths)}
    except (RuntimeError, ValueError, OSError) as exc:
        return {"error": str(exc)}


def concordance_search_tool(
    query: str,
    language: str | None = None,
    source_kind: str | None = None,
    max_results: int = 50,
) -> dict[str, Any]:
    """Run a literal FTS5 search and return hits.

    Args:
        query: FTS5 syntax — phrase ("..."), AND/OR/NEAR. NOT regex.
        language: optional ISO code filter.
        source_kind: 'nwt' | 'jwpub' | 'epub' to scope the search.
        max_results: cap (default 50, hard-cap 500).

    Returns:
        {"hits": [{"source_kind", "ref", "snippet", "language", "url"}, ...]}
        or {"error": "..."}.
    """

    try:
        hits = concordance_search(
            query,
            language=language,
            source_kind=source_kind,
            max_results=min(int(max_results), 500),
        )
        return {
            "hits": [
                {
                    "entry_id": h.entry_id,
                    "source_kind": h.source_kind,
                    "source_id": h.source_id,
                    "ref": h.ref,
                    "snippet": h.snippet,
                    "language": h.language,
                    "url": h.url,
                }
                for h in hits
            ]
        }
    except (RuntimeError, ValueError) as exc:
        return {"error": str(exc)}
