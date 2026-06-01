"""Tests for Compiler orchestrator."""

from __future__ import annotations

import json
from pathlib import Path

from jw_brain.backends import get_backend
from jw_brain.compiler.llm_extractor import LLMExtractor
from jw_brain.compiler.orchestrator import CompileOptions, Compiler
from jw_brain.schema import EdgeRegistry, NodeRegistry
from jw_brain.schema.builtins import register_tj_domain
from jw_brain.wiki.obsidian_writer import ObsidianWikiWriter


class FakeProvider:
    def __init__(self) -> None:
        self.calls = 0

    @property
    def id(self) -> str:
        return "fake"

    async def complete(self, prompt: str, *, temperature: float = 0.0) -> str:
        self.calls += 1
        return json.dumps({
            "nodes": [
                {"node_type": "Verse", "canonical_id": "verse:43:3:16",
                 "properties": {"book_num": 43, "chapter": 3, "verse": 16,
                                "text": "Porque Dios amó tanto al mundo", "language": "es"},
                 "confidence": 0.95},
                {"node_type": "Topic", "canonical_id": "topic:amor-de-dios",
                 "properties": {"slug": "amor-de-dios", "title": "Amor de Dios", "language": "es"},
                 "confidence": 0.9},
            ],
            "edges": [
                {"edge_type": "ABOUT", "from_node": "verse:43:3:16",
                 "to_node": "topic:amor-de-dios", "confidence": 0.85},
            ],
        })


def _setup(tmp_path: Path):
    vault = tmp_path / "vault"
    (vault / ".obsidian").mkdir(parents=True)
    backend = get_backend("duckdb", path=tmp_path / "backend.duckdb")
    nreg, ereg = NodeRegistry(), EdgeRegistry()
    register_tj_domain(nreg, ereg)
    provider = FakeProvider()
    extractor = LLMExtractor(provider=provider, node_registry=nreg, edge_registry=ereg)
    writer = ObsidianWikiWriter(vault_path=vault, namespace="Second-Brain")
    return backend, extractor, writer, nreg, ereg, vault, provider


async def test_compile_creates_nodes_edges_and_pages(tmp_path: Path) -> None:
    backend, extractor, writer, nreg, ereg, vault, _ = _setup(tmp_path)
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    sample = inbox / "note.md"
    sample.write_text("Porque Dios amó tanto al mundo (Juan 3:16).", encoding="utf-8")
    processed = tmp_path / "processed"

    compiler = Compiler(
        backend=backend, extractor=extractor, wiki_writer=writer,
        node_registry=nreg, edge_registry=ereg, cache_dir=tmp_path / "cache",
    )

    report = await compiler.compile(
        CompileOptions(inbox=inbox, processed=processed, language="es"),
    )

    assert report.n_files_processed == 1
    assert report.n_nodes_new >= 2
    assert report.n_edges_new >= 1
    assert (vault / "Second-Brain" / "verses").exists()
    assert (processed / "note.md").exists()
    assert not sample.exists()


async def test_dry_run_does_not_mutate(tmp_path: Path) -> None:
    backend, extractor, writer, nreg, ereg, vault, _ = _setup(tmp_path)
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    sample = inbox / "note.md"
    sample.write_text("Juan 3:16 — Porque Dios amó", encoding="utf-8")

    compiler = Compiler(
        backend=backend, extractor=extractor, wiki_writer=writer,
        node_registry=nreg, edge_registry=ereg, cache_dir=tmp_path / "cache",
    )

    report = await compiler.compile(CompileOptions(
        inbox=inbox, processed=tmp_path / "processed", language="es", dry_run=True,
    ))
    assert report.dry_run is True
    assert backend.stats()["n_nodes"] == 0
    assert sample.exists()


async def test_compile_cache_skips_second_run(tmp_path: Path) -> None:
    backend, extractor, writer, nreg, ereg, _, provider = _setup(tmp_path)
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    (inbox / "note.md").write_text("x" * 100, encoding="utf-8")
    processed = tmp_path / "processed"

    compiler = Compiler(
        backend=backend, extractor=extractor, wiki_writer=writer,
        node_registry=nreg, edge_registry=ereg, cache_dir=tmp_path / "cache",
    )

    await compiler.compile(CompileOptions(inbox=inbox, processed=processed, language="es"))
    first_calls = provider.calls

    (inbox / "note.md").write_text("x" * 100, encoding="utf-8")
    report2 = await compiler.compile(CompileOptions(inbox=inbox, processed=processed, language="es"))
    assert provider.calls == first_calls  # cache hit, no new LLM call
    assert report2.n_cache_hits == 1
