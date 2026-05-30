"""Tests for the finetuned_assistant agent."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from jw_agents.finetuned_assistant import finetuned_assistant
from jw_agents.finetuned_model import (
    FinetunedModelClient,
    GenerateRequest,
    GenerateResponse,
    build_client,
)


# ---------------------------------------------------------------------------
# Fake client
# ---------------------------------------------------------------------------


@dataclass
class FakeClient:
    text: str = "Respuesta generada de prueba."
    backend: str = "fake"
    model: str = "fake-1"

    def generate(self, req: GenerateRequest) -> GenerateResponse:
        return GenerateResponse(
            text=self.text,
            backend=self.backend,
            model=self.model,
            usage={"input_tokens": 10, "output_tokens": 20},
        )


@dataclass
class _Chunk:
    text: str
    metadata: dict[str, Any]


@dataclass
class _Hit:
    chunk: _Chunk
    score: float


class FakeRAGStore:
    """Minimal stand-in for jw_rag.store.VectorStore."""

    def __init__(self, hits: list[_Hit]) -> None:
        self._hits = hits

    def search(self, query: str, *, top_k: int = 3) -> list[_Hit]:
        return self._hits[:top_k]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_assistant_without_rag() -> None:
    client = FakeClient()
    result = finetuned_assistant(
        "¿Qué es el Reino?",
        client=client,
        rag_store=None,
        language="es",
    )
    assert result.agent_name == "finetuned_assistant"
    assert result.metadata["generated_answer"] == client.text
    assert result.metadata["backend"] == "fake"
    assert result.findings == []


def test_assistant_with_rag_hits() -> None:
    hits = [
        _Hit(_Chunk("El Reino es el gobierno celestial de Dios.",
                    {"pub_code": "w24", "section_ref": "w24 12 p.7",
                     "kind": "watchtower"}),
             0.95),
        _Hit(_Chunk("Daniel 2:44 lo profetiza.",
                    {"pub_code": "nwt", "section_ref": "Dan 2:44",
                     "kind": "bible"}),
             0.88),
    ]
    result = finetuned_assistant(
        "¿Qué es el Reino?",
        client=FakeClient(),
        rag_store=FakeRAGStore(hits),
        top_k=2,
        language="es",
    )
    assert len(result.findings) == 2
    assert result.findings[0].citation.kind == "watchtower"
    assert result.findings[1].citation.kind == "bible"
    # Generated answer is still present
    assert result.metadata["generated_answer"] != ""


def test_assistant_handles_rag_error() -> None:
    class BrokenStore:
        def search(self, query: str, **kw):
            raise RuntimeError("index missing")

    result = finetuned_assistant(
        "test",
        client=FakeClient(),
        rag_store=BrokenStore(),
    )
    assert any("RAG search failed" in w for w in result.warnings)
    # Generation still ran
    assert result.metadata["generated_answer"] != ""


def test_assistant_handles_client_error() -> None:
    class BrokenClient:
        backend = "broken"
        model = "x"

        def generate(self, req: GenerateRequest) -> GenerateResponse:
            raise RuntimeError("model down")

    result = finetuned_assistant("test", client=BrokenClient())
    assert result.metadata["generated_answer"] == ""
    assert any("model generation failed" in w for w in result.warnings)


def test_build_client_unknown_backend_raises() -> None:
    import pytest
    with pytest.raises(ValueError, match="Unknown backend"):
        build_client(backend="totally-fake")


def test_build_client_unsloth_requires_checkpoint() -> None:
    import pytest
    with pytest.raises(ValueError, match="checkpoint_dir"):
        build_client(backend="unsloth", checkpoint_dir=None)
