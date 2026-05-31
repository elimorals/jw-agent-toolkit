"""Reranker Protocol + factory."""

from __future__ import annotations

import logging
import os
from typing import Literal, Protocol, runtime_checkable

logger = logging.getLogger(__name__)

Target = Literal["api", "mlx", "nvidia", "cpu"]

PROVIDER_ORDER_DEFAULT: list[Target] = ["api", "mlx", "nvidia", "cpu"]
ENV_RERANK = "JW_RERANK_PROVIDER"
ENV_PROVIDER_ORDER = "JW_PROVIDER_ORDER"


@runtime_checkable
class Reranker(Protocol):
    """Canonical reranker contract.

    `rerank(query, candidates)` returns one score per candidate where higher
    means more relevant. Scores are NOT required to be probabilities; consumers
    only use them for sorting.
    """

    name: str
    target: Target

    def is_available(self) -> bool: ...

    def rerank(self, query: str, candidates: list[str]) -> list[float]: ...


class NoOpReranker:
    """Passthrough reranker — every candidate gets the same score.

    Used as the always-available fallback so `hybrid_search(rerank=True)` is
    bit-identical to `rerank=False` when no real reranker is configured.
    """

    name = "noop"
    target: Target = "cpu"

    def is_available(self) -> bool:
        return True

    def rerank(self, query: str, candidates: list[str]) -> list[float]:
        return [1.0] * len(candidates)


def _provider_order() -> list[Target]:
    raw = os.getenv(ENV_PROVIDER_ORDER, "")
    if not raw.strip():
        return PROVIDER_ORDER_DEFAULT
    parts: list[Target] = []
    for piece in raw.split(","):
        piece = piece.strip()
        if piece in {"api", "mlx", "nvidia", "cpu"}:
            parts.append(piece)  # type: ignore[arg-type]
    return parts or PROVIDER_ORDER_DEFAULT


def _instantiate_registry() -> list[Reranker]:
    from jw_rag.rerank_providers.bge_v2_m3 import BGERerankerV2M3Provider
    from jw_rag.rerank_providers.cohere_rerank import CohereRerankV35Provider
    from jw_rag.rerank_providers.fakes import (
        FakeBGEReranker,
        FakeCohereReranker,
        FakeJinaReranker,
    )
    from jw_rag.rerank_providers.jina_rerank import JinaRerankerV2Provider

    return [
        CohereRerankV35Provider(),
        JinaRerankerV2Provider(),
        BGERerankerV2M3Provider(),
        FakeBGEReranker(),
        FakeCohereReranker(),
        FakeJinaReranker(),
        NoOpReranker(),
    ]


def _named_lookup(name: str) -> Reranker | None:
    is_fake = name.startswith("fake-")
    bare = name.removeprefix("fake-")
    for r in _instantiate_registry():
        if r.name != bare:
            continue
        if is_fake and type(r).__module__.endswith(".fakes"):
            return r
        if not is_fake and not type(r).__module__.endswith(".fakes"):
            return r
    return None


def list_available_rerankers() -> list[Reranker]:
    order = _provider_order()
    # Exclude fakes from the public listing — they're selectable via explicit
    # JW_RERANK_PROVIDER=fake-* only (handled by `_named_lookup`).
    rs = [r for r in _instantiate_registry() if r.is_available() and not type(r).__module__.endswith(".fakes")]
    return sorted(rs, key=lambda r: order.index(r.target) if r.target in order else len(order))


def get_default_reranker() -> Reranker:
    env_name = os.getenv(ENV_RERANK, "").strip()
    if env_name:
        r = _named_lookup(env_name)
        if r is None:
            raise ValueError(f"unknown JW_RERANK_PROVIDER={env_name!r}")
        return r
    # Pick first available that's NOT the NoOp passthrough — NoOp is the fallback.
    for r in list_available_rerankers():
        if r.name != "noop":
            return r
    return NoOpReranker()
