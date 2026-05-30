"""Tests for the synth orchestrator using a fake LLM provider."""

from __future__ import annotations

import json
from dataclasses import dataclass

from jw_rag.chunker import Chunk

from jw_finetune.synth.orchestrator import SynthResult, synthesize_chunk
from jw_finetune.synth.provider import LLMRequest, LLMResponse


@dataclass
class FakeProvider:
    """Returns a fixed text on every call. Implements LLMProvider Protocol."""

    response_text: str
    name: str = "fake"
    model: str = "fake-1"

    def generate(self, req: LLMRequest) -> LLMResponse:
        return LLMResponse(
            text=self.response_text,
            provider=self.name,
            model=self.model,
            usage={"input_tokens": 10, "output_tokens": 50},
        )


def _chunk(text: str | None = None) -> Chunk:
    return Chunk(
        id="w24:1#0",
        text=text or "El Reino de Dios es el gobierno celestial. Daniel 2:44 lo profetiza.",
        source_id="w24:1",
        metadata={
            "language": "es",
            "pub_code": "w24",
            "section_ref": "w24 1 p.5",
        },
    )


def test_orchestrator_parses_valid_json() -> None:
    txt = json.dumps({
        "pairs": [
            {
                "q": "¿Qué es el Reino?",
                "a": "El Reino es el gobierno celestial mencionado en Daniel 2:44.",
            },
        ]
    })
    result = synthesize_chunk(
        _chunk(), provider=FakeProvider(txt),
        qa_style="doctrinal", language="es", n_pairs=1,
    )
    assert isinstance(result, SynthResult)
    assert len(result.pairs) == 1
    assert "Reino" in result.pairs[0].question
    assert result.parse_error is False
    assert result.usage["output_tokens"] == 50


def test_orchestrator_strips_markdown_fences() -> None:
    txt = (
        "```json\n"
        + json.dumps({"pairs": [
            {"q": "¿Cuál es el propósito?",
             "a": "El propósito es santificar el nombre de Jehová Dios."}
        ]})
        + "\n```"
    )
    result = synthesize_chunk(
        _chunk(), provider=FakeProvider(txt),
        qa_style="doctrinal", language="es",
    )
    assert len(result.pairs) == 1


def test_orchestrator_handles_malformed_json() -> None:
    result = synthesize_chunk(
        _chunk(), provider=FakeProvider("no soy json válido"),
        qa_style="doctrinal", language="es",
    )
    assert result.pairs == []
    assert result.parse_error is True
    assert result.rejected == 0


def test_orchestrator_rejects_too_short_pair() -> None:
    txt = json.dumps({"pairs": [{"q": "x", "a": "y"}]})
    result = synthesize_chunk(
        _chunk(), provider=FakeProvider(txt),
        qa_style="doctrinal", language="es",
    )
    assert result.pairs == []
    assert result.rejected == 1


def test_orchestrator_unknown_qa_style_raises() -> None:
    import pytest
    with pytest.raises(ValueError, match="Unknown qa_style"):
        synthesize_chunk(
            _chunk(), provider=FakeProvider("{}"),
            qa_style="unknown-style", language="es",
        )


def test_orchestrator_propagates_metadata() -> None:
    txt = json.dumps({"pairs": [
        {"q": "¿Cuándo se profetizó el Reino?",
         "a": "Daniel 2:44 profetiza el Reino como un gobierno que jamás será destruido."},
    ]})
    result = synthesize_chunk(
        _chunk(), provider=FakeProvider(txt),
        qa_style="doctrinal", language="es",
    )
    assert len(result.pairs) == 1
    qa = result.pairs[0]
    assert qa.source_chunk_id == "w24:1#0"
    assert qa.metadata["pub_code"] == "w24"
    assert qa.metadata["qa_style"] == "doctrinal"
    assert qa.language == "es"
