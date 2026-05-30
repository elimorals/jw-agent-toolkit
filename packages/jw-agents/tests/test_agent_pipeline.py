"""Tests for the agent_pipeline composers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest

from jw_agents.base import AgentResult, Citation, Finding
from jw_agents.finetuned_model import GenerateRequest, GenerateResponse


@dataclass
class FakeFinetunedClient:
    text: str = "El Reino es el gobierno celestial mencionado en Daniel 2:44."
    backend: str = "fake"
    model: str = "fake-1"

    def generate(self, req: GenerateRequest) -> GenerateResponse:
        return GenerateResponse(
            text=self.text, backend=self.backend, model=self.model,
            usage={"input_tokens": 5, "output_tokens": 20},
        )


@pytest.mark.asyncio
async def test_findings_to_context_extracts_excerpts() -> None:
    from jw_agents.agent_pipeline import _findings_to_context

    result = AgentResult(query="x", agent_name="x")
    result.findings.append(Finding(
        summary="resumen corto",
        excerpt="excerpt completo del párrafo del estudio",
        citation=Citation(url="http://wol/x", title="w24 12 p.7", kind="article"),
    ))
    result.findings.append(Finding(
        summary="otro resumen",
        citation=Citation(url="http://wol/y", title="g23 5 p.3", kind="article"),
    ))
    ctx = _findings_to_context(result)
    assert len(ctx) == 2
    assert "[w24 12 p.7]" in ctx[0]
    assert "excerpt completo" in ctx[0]
    # Second has no excerpt → falls back to summary
    assert "otro resumen" in ctx[1]


@pytest.mark.asyncio
async def test_verse_explainer_with_finetuned_calls_client(monkeypatch) -> None:
    """The pipeline should call both verse_explainer AND the client."""
    # `jw_agents.verse_explainer` is shadowed by the function in __init__.py;
    # access the module via sys.modules.
    import sys
    ve_mod = sys.modules["jw_agents.verse_explainer"]
    from jw_agents import agent_pipeline

    captured_client_calls: list[str] = []

    class CaptureClient:
        backend = "capture"
        model = "x"
        def generate(self, req: GenerateRequest) -> GenerateResponse:
            captured_client_calls.append(req.prompt)
            return GenerateResponse(
                text="generated answer here.",
                backend=self.backend, model=self.model,
                usage={"input_tokens": 1, "output_tokens": 1},
            )

    # Fake verse_explainer that returns a known AgentResult
    async def fake_verse_explainer(text, **kw):
        ar = AgentResult(query=text, agent_name="verse_explainer")
        ar.findings.append(Finding(
            summary="El versículo habla del amor de Dios.",
            excerpt="«Porque tanto amó Dios al mundo...»",
            citation=Citation(url="http://wol/jn3", title="Juan 3:16", kind="verse"),
        ))
        return ar

    monkeypatch.setattr(ve_mod, "verse_explainer", fake_verse_explainer)

    result = await agent_pipeline.verse_explainer_with_finetuned(
        "Juan 3:16",
        finetuned_client=CaptureClient(),
        language="es",
    )
    assert result.agent_name == "verse_explainer_with_finetuned"
    assert len(result.findings) == 1  # passed through from enricher
    assert result.metadata["generated_answer"] == "generated answer here."
    assert len(captured_client_calls) == 1
    assert "Juan 3:16" in captured_client_calls[0]
    # The context was included in the prompt
    assert "tanto amó Dios" in captured_client_calls[0]


@pytest.mark.asyncio
async def test_verse_explainer_with_finetuned_handles_client_error(monkeypatch) -> None:
    import sys
    ve_mod = sys.modules["jw_agents.verse_explainer"]
    from jw_agents import agent_pipeline

    class BrokenClient:
        backend = "broken"
        model = "x"
        def generate(self, req): raise RuntimeError("model down")

    async def fake_verse_explainer(text, **kw):
        return AgentResult(query=text, agent_name="verse_explainer")

    monkeypatch.setattr(ve_mod, "verse_explainer", fake_verse_explainer)

    result = await agent_pipeline.verse_explainer_with_finetuned(
        "Juan 3:16",
        finetuned_client=BrokenClient(),
        language="es",
    )
    assert result.metadata["generated_answer"] == ""
    assert any("finetuned generation failed" in w for w in result.warnings)


@pytest.mark.asyncio
async def test_conversation_assistant_with_finetuned(monkeypatch) -> None:
    import sys
    ca_mod = sys.modules["jw_agents.conversation_assistant"]
    from jw_agents import agent_pipeline

    async def fake_ca(text, **kw):
        ar = AgentResult(query=text, agent_name="conversation_assistant")
        ar.findings.append(Finding(
            summary="Texto sobre la Trinidad",
            citation=Citation(url="http://wol/x", title="bh ch.4", kind="article"),
        ))
        return ar

    monkeypatch.setattr(ca_mod, "conversation_assistant", fake_ca)

    result = await agent_pipeline.conversation_assistant_with_finetuned(
        "¿Por qué no creen en la Trinidad?",
        finetuned_client=FakeFinetunedClient(),
        language="es",
    )
    assert result.agent_name == "conversation_assistant_with_finetuned"
    assert result.metadata["generated_answer"]
