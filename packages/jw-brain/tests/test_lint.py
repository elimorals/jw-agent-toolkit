"""Tests for lint operations."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from jw_brain.backends import get_backend
from jw_brain.lint.contradiction_finder import ContradictionFinder
from jw_brain.lint.orphan_pages import find_orphan_pages


@dataclass
class _NLIVerdict:
    label: str
    score: float


class FakeNLI:
    """Returns 'contradicts' deterministically."""

    def __init__(self, label: str = "contradicts", score: float = 0.9) -> None:
        self.label = label
        self.score = score
        self.calls = 0

    async def evaluate_entailment(self, claim: str, premise: str) -> Any:
        self.calls += 1
        return _NLIVerdict(label=self.label, score=self.score)


async def test_contradiction_finder_detects_pair(tmp_path: Path) -> None:
    backend = get_backend("duckdb", path=tmp_path / "g.duckdb")
    backend.upsert_node(
        node_type="Topic", canonical_id="topic:trinity",
        properties={"slug": "trinity"}, provenance={},
    )
    backend.upsert_node(
        node_type="Publication", canonical_id="pub:a",
        properties={"title": "Dios es uno solo"}, provenance={},
    )
    backend.upsert_node(
        node_type="Publication", canonical_id="pub:b",
        properties={"title": "Dios es trino"}, provenance={},
    )
    backend.upsert_edge(
        edge_type="EXPANDS", from_node="pub:a", to_node="topic:trinity",
        properties={}, provenance={},
    )
    backend.upsert_edge(
        edge_type="EXPANDS", from_node="pub:b", to_node="topic:trinity",
        properties={}, provenance={},
    )

    finder = ContradictionFinder(nli_provider=FakeNLI(), backend=backend)
    results = await finder.find(threshold=0.5)
    assert len(results) == 1
    assert {results[0].source_a, results[0].source_b} == {"pub:a", "pub:b"}


async def test_contradiction_finder_below_threshold_skipped(tmp_path: Path) -> None:
    backend = get_backend("duckdb", path=tmp_path / "g.duckdb")
    backend.upsert_node(
        node_type="Topic", canonical_id="topic:x",
        properties={"slug": "x"}, provenance={},
    )
    backend.upsert_node(
        node_type="Publication", canonical_id="pub:a",
        properties={"title": "A"}, provenance={},
    )
    backend.upsert_node(
        node_type="Publication", canonical_id="pub:b",
        properties={"title": "B"}, provenance={},
    )
    backend.upsert_edge(edge_type="EXPANDS", from_node="pub:a", to_node="topic:x", properties={}, provenance={})
    backend.upsert_edge(edge_type="EXPANDS", from_node="pub:b", to_node="topic:x", properties={}, provenance={})

    finder = ContradictionFinder(nli_provider=FakeNLI(score=0.3), backend=backend)
    assert await finder.find(threshold=0.7) == []


def test_orphan_pages_detects_unwired_wiki(tmp_path: Path) -> None:
    backend = get_backend("duckdb", path=tmp_path / "g.duckdb")
    wiki_root = tmp_path / "Second-Brain"
    wiki_root.mkdir()
    (wiki_root / "verses").mkdir()
    (wiki_root / "verses" / "orphan.md").write_text(
        "---\ncanonical_id: verse:1:1:1\nnode_type: Verse\n---\n\nbody\n",
        encoding="utf-8",
    )
    (wiki_root / "verses" / "connected.md").write_text(
        "---\ncanonical_id: verse:43:3:16\nnode_type: Verse\n---\n\nbody\n",
        encoding="utf-8",
    )

    # connected verse has an edge in the graph
    backend.upsert_node(node_type="Verse", canonical_id="verse:43:3:16", properties={}, provenance={})
    backend.upsert_node(node_type="Topic", canonical_id="topic:x", properties={}, provenance={})
    backend.upsert_edge(edge_type="ABOUT", from_node="verse:43:3:16", to_node="topic:x", properties={}, provenance={})

    orphans = find_orphan_pages(wiki_root=wiki_root, backend=backend)
    names = [p.name for p in orphans]
    assert "orphan.md" in names
    assert "connected.md" not in names


def test_orphan_pages_skips_log_and_index(tmp_path: Path) -> None:
    backend = get_backend("duckdb", path=tmp_path / "g.duckdb")
    wiki_root = tmp_path / "Second-Brain"
    wiki_root.mkdir()
    (wiki_root / "index.md").write_text("# Index", encoding="utf-8")
    (wiki_root / "log.md").write_text("# Log", encoding="utf-8")

    orphans = find_orphan_pages(wiki_root=wiki_root, backend=backend)
    assert orphans == []
