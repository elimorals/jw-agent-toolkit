"""GraphBackend Protocol — backend-agnostic graph store."""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator, Protocol, runtime_checkable


@runtime_checkable
class GraphBackend(Protocol):
    name: str

    def upsert_node(
        self,
        *,
        node_type: str,
        canonical_id: str,
        properties: dict[str, Any],
        provenance: dict[str, Any],
    ) -> str: ...

    def upsert_edge(
        self,
        *,
        edge_type: str,
        from_node: str,
        to_node: str,
        properties: dict[str, Any],
        provenance: dict[str, Any],
    ) -> str: ...

    @contextmanager
    def transaction(self) -> Iterator[None]: ...

    def get_node(self, canonical_id: str) -> dict[str, Any] | None: ...

    def neighbors(
        self,
        canonical_id: str,
        *,
        edge_type: str | None = None,
        hops: int = 1,
        direction: str = "both",
    ) -> list[dict[str, Any]]: ...

    def query(
        self,
        expr: str,
        params: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]: ...

    def snapshot(self, path: Path) -> None: ...
    def restore(self, path: Path) -> None: ...
    def stats(self) -> dict[str, Any]: ...
