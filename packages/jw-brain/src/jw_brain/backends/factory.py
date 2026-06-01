"""Backend factory."""

from __future__ import annotations

import os
from typing import Any

from jw_brain.backends.protocol import GraphBackend


def get_backend(name: str | None = None, **kwargs: Any) -> GraphBackend:
    """Resolve a GraphBackend by name, env var, or default (duckdb)."""

    resolved = name or os.environ.get("JW_BRAIN_BACKEND", "duckdb")
    if resolved == "duckdb":
        from jw_brain.backends.duckdb_backend import DuckDBBackend

        return DuckDBBackend(**kwargs)
    if resolved == "neo4j":
        from jw_brain.backends.neo4j_backend import Neo4jBackend

        return Neo4jBackend(**kwargs)
    raise ValueError(f"Unknown backend: {resolved!r}")
