"""F49 Second Brain → drift Chunk adapter tests (Fase 72)."""

from __future__ import annotations

from typing import Any

import numpy as np

from jw_core.drift.brain_source import chunks_from_brain


class _FakeBackend:
    def __init__(self, nodes: list[dict[str, Any]]) -> None:
        self._nodes = nodes

    def list_nodes(self, *, node_type: str) -> list[dict[str, Any]]:
        return [n for n in self._nodes if n.get("node_type") == node_type]


def _embed(text: str) -> np.ndarray:
    rng = np.random.default_rng(abs(hash(text)) % (2**32))
    v = rng.standard_normal(8).astype(np.float32)
    return v


def test_chunks_from_brain_extracts_year_from_published_date() -> None:
    backend = _FakeBackend(
        [
            {
                "canonical_id": "pub:w85:es",
                "node_type": "Publication",
                "properties": {
                    "text": "Una explicación de la doctrina del alma " * 3,
                    "published_date": "1985-04-15",
                    "language": "es",
                },
            }
        ]
    )
    chunks = chunks_from_brain(backend, embed=_embed)
    assert len(chunks) == 1
    assert chunks[0].year == 1985
    assert abs(float(np.linalg.norm(chunks[0].embedding)) - 1.0) < 1e-5


def test_chunks_from_brain_uses_explicit_year_field() -> None:
    backend = _FakeBackend(
        [
            {
                "canonical_id": "pub:x:es",
                "node_type": "Publication",
                "properties": {
                    "summary": "Texto largo sobre la resurrección " * 3,
                    "year": 2024,
                },
            }
        ]
    )
    chunks = chunks_from_brain(backend, embed=_embed)
    assert len(chunks) == 1
    assert chunks[0].year == 2024


def test_chunks_from_brain_skips_when_year_missing() -> None:
    backend = _FakeBackend(
        [
            {
                "canonical_id": "pub:nodate:es",
                "node_type": "Publication",
                "properties": {"text": "X" * 200},
            }
        ]
    )
    assert chunks_from_brain(backend, embed=_embed) == []


def test_chunks_from_brain_skips_short_text() -> None:
    backend = _FakeBackend(
        [
            {
                "canonical_id": "pub:tiny:es",
                "node_type": "Publication",
                "properties": {"text": "hi", "year": 2000},
            }
        ]
    )
    assert chunks_from_brain(backend, embed=_embed) == []


def test_chunks_from_brain_language_filter() -> None:
    backend = _FakeBackend(
        [
            {
                "canonical_id": "pub:es:es",
                "node_type": "Publication",
                "properties": {
                    "text": "Texto largo en español " * 3,
                    "year": 2020,
                    "language": "es",
                },
            },
            {
                "canonical_id": "pub:en:en",
                "node_type": "Publication",
                "properties": {
                    "text": "Long english text " * 3,
                    "year": 2020,
                    "language": "en",
                },
            },
        ]
    )
    chunks = chunks_from_brain(backend, embed=_embed, language="es")
    assert len(chunks) == 1
    assert chunks[0].text.startswith("Texto")


def test_chunks_from_brain_filters_node_type() -> None:
    backend = _FakeBackend(
        [
            {
                "canonical_id": "topic:alma",
                "node_type": "Topic",
                "properties": {
                    "title": "Alma",
                    "year": 2020,
                    "text": "Topic text " * 5,
                },
            }
        ]
    )
    # default node_type=Publication, Topic is skipped
    assert chunks_from_brain(backend, embed=_embed) == []
    # explicit override picks them up
    chunks = chunks_from_brain(backend, embed=_embed, node_type="Topic")
    assert len(chunks) == 1
