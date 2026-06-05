"""Tests for LLMExtractor with deterministic FakeProvider."""

from __future__ import annotations

import json
from dataclasses import dataclass, field

import pytest
from jw_brain.compiler.cache import ExtractionCache, cache_key_for
from jw_brain.compiler.llm_extractor import (
    ExtractionRequest,
    LLMExtractor,
)
from jw_brain.schema import EdgeRegistry, NodeRegistry
from jw_brain.schema.builtins import register_tj_domain


@dataclass
class FakeGenProvider:
    canned_output: str
    call_log: list[str] = field(default_factory=list)

    @property
    def id(self) -> str:
        return "fake:canned"

    async def complete(self, prompt: str, *, temperature: float = 0.0) -> str:
        self.call_log.append(prompt)
        return self.canned_output


@pytest.fixture
def registries():
    n, e = NodeRegistry(strict=False), EdgeRegistry()
    register_tj_domain(n, e)
    return n, e


async def test_extractor_parses_canned_json(registries) -> None:
    nreg, ereg = registries
    canned = json.dumps({
        "nodes": [
            {"node_type": "Verse", "canonical_id": "verse:43:3:16",
             "properties": {"book_num": 43, "chapter": 3, "verse": 16, "text": "..."},
             "confidence": 0.95},
        ],
        "edges": [
            {"edge_type": "ABOUT", "from_node": "verse:43:3:16",
             "to_node": "topic:amor-de-dios", "confidence": 0.8},
        ],
    })
    extractor = LLMExtractor(provider=FakeGenProvider(canned), node_registry=nreg, edge_registry=ereg)
    result = await extractor.extract(ExtractionRequest(
        chunks=["Porque Dios amó tanto al mundo..."],
        source_chunk_id="src:1",
        language="es",
        run_id="r1",
    ))
    assert len(result.nodes) == 1
    assert result.nodes[0].canonical_id == "verse:43:3:16"
    assert result.edges[0].edge_type == "ABOUT"


async def test_extractor_filters_unknown_node_types(registries) -> None:
    nreg, ereg = registries
    canned = json.dumps({
        "nodes": [
            {"node_type": "BogusType", "canonical_id": "bogus:1",
             "properties": {}, "confidence": 0.5},
        ],
        "edges": [],
    })
    extractor = LLMExtractor(provider=FakeGenProvider(canned), node_registry=nreg, edge_registry=ereg)
    result = await extractor.extract(ExtractionRequest(
        chunks=["..."], source_chunk_id="src:1", language="es", run_id="r1",
    ))
    assert len(result.nodes) == 0
    assert any("BogusType" in w for w in result.warnings)


async def test_extractor_low_confidence_marked(registries) -> None:
    nreg, ereg = registries
    canned = json.dumps({
        "nodes": [
            {"node_type": "Verse", "canonical_id": "verse:43:3:16",
             "properties": {"book_num": 43, "chapter": 3, "verse": 16, "text": "..."},
             "confidence": 0.4},
        ],
        "edges": [],
    })
    extractor = LLMExtractor(provider=FakeGenProvider(canned), node_registry=nreg, edge_registry=ereg)
    result = await extractor.extract(ExtractionRequest(
        chunks=["..."], source_chunk_id="src:1", language="es", run_id="r1",
    ))
    assert result.nodes[0].low_confidence is True


async def test_extractor_handles_non_json_gracefully(registries) -> None:
    nreg, ereg = registries
    extractor = LLMExtractor(provider=FakeGenProvider("not json {"), node_registry=nreg, edge_registry=ereg)
    result = await extractor.extract(ExtractionRequest(
        chunks=["x"], source_chunk_id="s", language="es", run_id="r",
    ))
    assert result.nodes == []
    assert any("non-JSON" in w for w in result.warnings)


def test_cache_key_stable() -> None:
    k1 = cache_key_for(content="x", prompt_version="v1", provider_id="fake")
    k2 = cache_key_for(content="x", prompt_version="v1", provider_id="fake")
    assert k1 == k2


def test_cache_key_differs_by_input() -> None:
    k1 = cache_key_for(content="x", prompt_version="v1", provider_id="fake")
    k2 = cache_key_for(content="y", prompt_version="v1", provider_id="fake")
    k3 = cache_key_for(content="x", prompt_version="v2", provider_id="fake")
    assert k1 != k2 and k1 != k3


def test_cache_roundtrip(tmp_path):
    cache = ExtractionCache(cache_dir=tmp_path)
    cache.put("k1", {"nodes": [], "edges": []})
    out = cache.get("k1")
    assert out == {"nodes": [], "edges": []}


def test_cache_miss_returns_none(tmp_path):
    cache = ExtractionCache(cache_dir=tmp_path)
    assert cache.get("missing") is None
