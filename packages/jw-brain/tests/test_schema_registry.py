"""Tests for schema-on-read registry."""

from __future__ import annotations

import pytest

from jw_brain.schema import (
    EdgeRegistry,
    EdgeTypeSpec,
    NodeRegistry,
    NodeTypeSpec,
    canonical_id_for,
)


def test_node_registry_register_and_get() -> None:
    reg = NodeRegistry()
    spec = NodeTypeSpec(
        name="Verse",
        canonical_id_pattern="verse:{book}:{ch}:{v}",
        properties={"book_num": int, "chapter": int, "verse": int, "text": str},
        wiki_page_template="verse.md",
        obsidian_subdir="verses/",
        confidence_threshold=0.7,
    )
    reg.register(spec)
    assert reg.get("Verse") is spec
    assert reg.get("Unknown") is None


def test_canonical_id_for_renders_pattern() -> None:
    spec = NodeTypeSpec(
        name="Verse",
        canonical_id_pattern="verse:{book}:{ch}:{v}",
        properties={}, wiki_page_template="", obsidian_subdir="",
    )
    assert canonical_id_for(spec, {"book": 43, "ch": 3, "v": 16}) == "verse:43:3:16"


def test_node_spec_unknown_property_rejected_when_strict() -> None:
    reg = NodeRegistry(strict=True)
    spec = NodeTypeSpec(
        name="Topic",
        canonical_id_pattern="topic:{slug}",
        properties={"slug": str, "title": str},
        wiki_page_template="", obsidian_subdir="",
    )
    reg.register(spec)
    with pytest.raises(ValueError, match="unknown property"):
        reg.validate("Topic", {"slug": "trinity", "bogus_field": 1})


def test_builtin_tj_domain_has_six_node_types() -> None:
    from jw_brain.schema.builtins import tj_node_specs
    names = {s.name for s in tj_node_specs()}
    assert {"Verse", "Topic", "Publication", "Concept", "Person", "Place"} <= names


def test_edge_registry_validates_source_target() -> None:
    edge_reg = EdgeRegistry()
    edge_reg.register(EdgeTypeSpec(
        name="CITED_IN",
        sources=("Verse", "Topic"),
        targets=("Publication",),
        directional=True,
        confidence_threshold=0.6,
    ))
    spec = edge_reg.get("CITED_IN")
    assert spec is not None
    assert "Publication" in spec.targets


def test_provenance_arista_has_required_fields() -> None:
    from jw_brain.schema.provenance import EdgeProvenance

    p = EdgeProvenance(
        run_id="abc-123",
        model_id="ollama:llama3.1:8b",
        prompt_version="v1",
        confidence=0.92,
        source_chunk_id="article:url#3",
        extracted_at="2026-06-01T10:00:00Z",
    )
    d = p.model_dump()
    assert d["run_id"] == "abc-123"
    assert d["confidence"] == 0.92


def test_register_tj_domain_populates_both_registries() -> None:
    from jw_brain.schema.builtins import register_tj_domain

    nreg, ereg = NodeRegistry(), EdgeRegistry()
    register_tj_domain(nreg, ereg)
    assert len(nreg.all()) == 6
    assert len(ereg.all()) == 6
