"""TJ domain — reference NodeTypes/EdgeTypes."""

from __future__ import annotations

from jw_brain.schema.edges import EdgeTypeSpec
from jw_brain.schema.nodes import NodeTypeSpec


def tj_node_specs() -> list[NodeTypeSpec]:
    return [
        NodeTypeSpec(
            name="Verse",
            canonical_id_pattern="verse:{book}:{ch}:{v}",
            properties={"book_num": int, "chapter": int, "verse": int, "text": str, "language": str},
            wiki_page_template="verse.md",
            obsidian_subdir="verses/",
            confidence_threshold=0.9,
        ),
        NodeTypeSpec(
            name="Topic",
            canonical_id_pattern="topic:{slug}",
            properties={"slug": str, "title": str, "language": str},
            wiki_page_template="topic.md",
            obsidian_subdir="topics/",
        ),
        NodeTypeSpec(
            name="Publication",
            canonical_id_pattern="pub:{pub_code}:{language}",
            properties={"pub_code": str, "title": str, "language": str, "published_date": str},
            wiki_page_template="publication.md",
            obsidian_subdir="publications/",
        ),
        NodeTypeSpec(
            name="Concept",
            canonical_id_pattern="concept:{slug}",
            properties={"slug": str, "title": str, "summary": str},
            wiki_page_template="concept.md",
            obsidian_subdir="concepts/",
        ),
        NodeTypeSpec(
            name="Person",
            canonical_id_pattern="person:{slug}",
            properties={"slug": str, "name": str, "era": str},
            wiki_page_template="person.md",
            obsidian_subdir="people/",
        ),
        NodeTypeSpec(
            name="Place",
            canonical_id_pattern="place:{slug}",
            properties={"slug": str, "name": str, "modern_name": str},
            wiki_page_template="place.md",
            obsidian_subdir="places/",
        ),
    ]


def tj_edge_specs() -> list[EdgeTypeSpec]:
    return [
        EdgeTypeSpec(name="CITED_IN", sources=("Verse", "Topic"), targets=("Publication",)),
        EdgeTypeSpec(name="MENTIONS", sources=("Publication",), targets=("Verse", "Topic", "Person", "Place")),
        EdgeTypeSpec(name="EXPANDS", sources=("Publication",), targets=("Topic", "Concept")),
        EdgeTypeSpec(name="CROSS_REFERENCES", sources=("Verse",), targets=("Verse",), directional=False),
        EdgeTypeSpec(name="CONTRADICTS", sources=("Publication",), targets=("Publication",), sensitive=True),
        EdgeTypeSpec(name="ABOUT", sources=("Verse",), targets=("Topic", "Concept", "Person", "Place")),
    ]


def register_tj_domain(node_registry, edge_registry) -> None:
    for spec in tj_node_specs():
        node_registry.register(spec)
    for spec in tj_edge_specs():
        edge_registry.register(spec)
