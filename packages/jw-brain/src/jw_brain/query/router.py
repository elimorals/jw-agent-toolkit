"""Query router — Karpathy-first, graph fallback, vector last resort."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class QueryStrategy(Enum):
    WIKI_FIRST = "wiki_first"
    GRAPH_FIRST = "graph_first"
    VECTOR_FALLBACK = "vector_fallback"


_MULTI_HOP_TOKENS = re.compile(
    r"\b(que conecte|a través de|que también|cross|también cit|también menciona|publicacion.* que cit)\b",
    re.IGNORECASE,
)
_CANONICAL_ENTITY = re.compile(r"\b(\w+ \d+:\d+|verse:\S+|topic:\S+|pub:\S+)\b")


@dataclass
class QueryRequest:
    question: str
    mode: str = "auto"  # "auto" | "wiki" | "graph" | "vector"
    k: int = 10


@dataclass
class QueryResult:
    answer: str | None = None
    citations: list[dict[str, Any]] = field(default_factory=list)
    strategy: str = ""
    confidence: float = 0.0


def detect_strategy(question: str) -> QueryStrategy:
    if _MULTI_HOP_TOKENS.search(question):
        return QueryStrategy.GRAPH_FIRST
    if _CANONICAL_ENTITY.search(question):
        return QueryStrategy.WIKI_FIRST
    return QueryStrategy.WIKI_FIRST


class QueryRouter:
    def __init__(
        self,
        *,
        wiki_searcher,
        graph_traverser,
        vector_fallback=None,
    ) -> None:
        self.wiki = wiki_searcher
        self.graph = graph_traverser
        self.vector = vector_fallback

    def query(self, req: QueryRequest) -> QueryResult:
        if req.mode == "wiki":
            strategy = QueryStrategy.WIKI_FIRST
        elif req.mode == "graph":
            strategy = QueryStrategy.GRAPH_FIRST
        elif req.mode == "vector":
            strategy = QueryStrategy.VECTOR_FALLBACK
        else:
            strategy = detect_strategy(req.question)

        if strategy is QueryStrategy.GRAPH_FIRST and self.graph is not None:
            result = self.graph.search(req.question, k=req.k)
        elif strategy is QueryStrategy.WIKI_FIRST and self.wiki is not None:
            result = self.wiki.search(req.question, k=req.k)
            if (not result.citations) and self.graph is not None:
                result = self.graph.search(req.question, k=req.k)
        else:
            if self.vector is not None:
                result = self.vector.search(req.question, k=req.k)
            else:
                result = QueryResult(strategy="vector", confidence=0.0)

        result.strategy = strategy.value
        return result
