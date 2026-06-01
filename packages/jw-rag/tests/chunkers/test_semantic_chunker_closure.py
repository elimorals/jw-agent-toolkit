"""SemanticChunker — closure split."""

from __future__ import annotations

from pathlib import Path

import pytest

from jw_rag.chunkers.semantic_chunker import SemanticChunker

FIXTURE = Path(__file__).parent / "fixtures" / "article_with_closure_es.txt"


def _paragraphs() -> list[str]:
    return [
        line.strip()
        for line in FIXTURE.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def test_closure_es_closes_chunk_after_por_lo_tanto() -> None:
    c = SemanticChunker(max_chars=500, min_chars=40)
    chunks = c.chunk(_paragraphs(), source_id="es_doc", metadata={"language": "es"})
    assert "Por lo tanto" in chunks[0].text
    assert "Premisa importante" in chunks[0].text
    assert chunks[0].metadata.get("closure_marker") == "Por lo tanto"
    assert any("Nuevo tema" in ch.text for ch in chunks[1:])
    assert "Nuevo tema" not in chunks[0].text


def test_closure_does_not_fire_below_min_chars() -> None:
    c = SemanticChunker(max_chars=500, min_chars=200)
    paragraphs = ["Tiny.", "Por lo tanto, esto seguiría junto a lo siguiente.", "Siguiente."]
    chunks = c.chunk(paragraphs, source_id="es", metadata={"language": "es"})
    assert len(chunks) == 1


def test_closure_en_therefore() -> None:
    c = SemanticChunker(max_chars=500, min_chars=40)
    paragraphs = [
        "The premise here is sufficiently lengthy for min_chars to be exceeded already.",
        "Therefore the argument concludes here cleanly.",
        "New unrelated topic begins.",
    ]
    chunks = c.chunk(paragraphs, source_id="en", metadata={"language": "en"})
    assert chunks[0].metadata.get("closure_marker") == "Therefore"
    assert "Therefore" in chunks[0].text
    assert any("New unrelated" in ch.text for ch in chunks[1:])


def test_closure_pt_portanto() -> None:
    c = SemanticChunker(max_chars=500, min_chars=40)
    paragraphs = [
        "A premissa precisa ser suficientemente longa para passar de min_chars sem problema.",
        "Portanto, a conclusão segue de modo inequívoco.",
        "Nova ideia começa aqui.",
    ]
    chunks = c.chunk(paragraphs, source_id="pt", metadata={"language": "pt"})
    assert chunks[0].metadata.get("closure_marker") == "Portanto"
    assert "Portanto" in chunks[0].text
    assert any("Nova ideia" in ch.text for ch in chunks[1:])


@pytest.mark.parametrize(
    ("language", "closure_marker", "expected_in_first_chunk"),
    [
        ("es", "En conclusión", "En conclusión"),
        ("en", "In conclusion", "In conclusion"),
        ("pt", "Em conclusão", "Em conclusão"),
    ],
)
def test_closure_alt_markers_per_language(
    language: str, closure_marker: str, expected_in_first_chunk: str,
) -> None:
    c = SemanticChunker(max_chars=400, min_chars=40)
    paragraphs = [
        "x" * 60,
        f"{closure_marker}, this paragraph concludes the argument.",
        "Subsequent unrelated content.",
    ]
    chunks = c.chunk(paragraphs, source_id="z", metadata={"language": language})
    assert expected_in_first_chunk in chunks[0].text
    assert chunks[0].metadata.get("closure_marker") == closure_marker
