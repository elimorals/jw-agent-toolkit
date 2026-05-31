"""Reranker Protocol + factory (stub — full implementation in Task 11)."""

from __future__ import annotations

from typing import Literal, Protocol, runtime_checkable

Target = Literal["api", "mlx", "nvidia", "cpu"]


@runtime_checkable
class Reranker(Protocol):
    name: str
    target: Target

    def is_available(self) -> bool: ...

    def rerank(self, query: str, candidates: list[str]) -> list[float]: ...


def get_default_reranker() -> Reranker:  # pragma: no cover - replaced in Task 11
    raise NotImplementedError("Implemented in Task 11")


def list_available_rerankers() -> list[Reranker]:  # pragma: no cover - replaced in Task 11
    raise NotImplementedError("Implemented in Task 11")
