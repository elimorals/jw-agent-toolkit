"""Tests for query router."""

from __future__ import annotations

from dataclasses import dataclass, field

from jw_brain.query.router import (
    QueryRequest,
    QueryResult,
    QueryRouter,
    QueryStrategy,
    detect_strategy,
)


def test_detect_multi_hop_signal() -> None:
    assert detect_strategy("Qué versículos se conectan a través de Eclesiastés") == QueryStrategy.GRAPH_FIRST


def test_detect_canonical_entity_goes_wiki_first() -> None:
    assert detect_strategy("Explica Juan 3:16") == QueryStrategy.WIKI_FIRST


def test_detect_default_is_wiki() -> None:
    assert detect_strategy("hola") == QueryStrategy.WIKI_FIRST


@dataclass
class _FakeWiki:
    canned_citations: list[dict] = field(default_factory=list)

    def search(self, question: str, *, k: int = 10) -> QueryResult:  # noqa: ARG002
        return QueryResult(answer="wiki", citations=list(self.canned_citations), confidence=0.8)


@dataclass
class _FakeGraph:
    canned_citations: list[dict] = field(default_factory=list)
    calls: list[str] = field(default_factory=list)

    def search(self, question: str, *, k: int = 10) -> QueryResult:
        self.calls.append(question)
        return QueryResult(answer="graph", citations=list(self.canned_citations), confidence=0.9)


def test_router_wiki_first_when_hits() -> None:
    wiki = _FakeWiki(canned_citations=[{"url": "x"}])
    graph = _FakeGraph()
    router = QueryRouter(wiki_searcher=wiki, graph_traverser=graph)
    result = router.query(QueryRequest(question="Explica Juan 3:16"))
    assert result.answer == "wiki"
    assert result.strategy == "wiki_first"
    assert graph.calls == []


def test_router_falls_back_to_graph_when_wiki_empty() -> None:
    wiki = _FakeWiki(canned_citations=[])
    graph = _FakeGraph(canned_citations=[{"url": "g"}])
    router = QueryRouter(wiki_searcher=wiki, graph_traverser=graph)
    result = router.query(QueryRequest(question="Explica Juan 3:16"))
    assert result.answer == "graph"
    assert graph.calls == ["Explica Juan 3:16"]


def test_router_graph_first_on_multi_hop_signal() -> None:
    wiki = _FakeWiki(canned_citations=[{"url": "x"}])  # wiki has hits
    graph = _FakeGraph(canned_citations=[{"url": "g"}])
    router = QueryRouter(wiki_searcher=wiki, graph_traverser=graph)
    result = router.query(QueryRequest(question="Qué se conecta a través de Eclesiastés 9:5"))
    assert result.answer == "graph"
    assert result.strategy == "graph_first"


def test_router_explicit_mode_wins() -> None:
    wiki = _FakeWiki(canned_citations=[{"url": "x"}])
    graph = _FakeGraph(canned_citations=[{"url": "g"}])
    router = QueryRouter(wiki_searcher=wiki, graph_traverser=graph)
    result = router.query(QueryRequest(question="Explica Juan 3:16", mode="graph"))
    assert result.strategy == "graph_first"
