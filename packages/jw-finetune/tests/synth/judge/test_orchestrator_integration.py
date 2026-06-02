"""Tests that synthesize_chunk routes pairs through an optional Judge."""

from __future__ import annotations

import json
from typing import Any

from jw_rag.chunker import Chunk

from jw_finetune.synth.judge import Judge, JudgeMode, JudgeOverrides
from jw_finetune.synth.orchestrator import synthesize_chunk
from jw_finetune.synth.provider import LLMRequest, LLMResponse


class FakeSynthProvider:
    name = "fake"
    model = "fake-synth"

    def __init__(self, payload: dict[str, Any]) -> None:
        self._payload = payload

    def generate(self, req: LLMRequest) -> LLMResponse:  # noqa: ARG002
        return LLMResponse(
            text=json.dumps(self._payload, ensure_ascii=False),
            provider=self.name,
            model=self.model,
            usage={"input_tokens": 50, "output_tokens": 100},
        )


def _chunk() -> Chunk:
    return Chunk(
        id="chunk_1",
        text="Algún texto fuente.",
        source_id="src_1",
        metadata={"pub_code": "w23", "section_ref": "p. 5"},
    )


def _payload_two_pairs() -> dict[str, Any]:
    return {
        "pairs": [
            {
                "q": "¿Qué enseña la Biblia sobre el reino?",
                "a": (
                    "Como muestra w23 página 5, el reino de Dios es un "
                    "gobierno real con Cristo Jesús como rey, según "
                    "Daniel 2:44 y Mateo 6:9-10."
                ),
            },
            {
                "q": "¿Otra pregunta?",
                "a": "Sí.",
            },
        ]
    }


def test_synthesize_chunk_without_judge_keeps_all_valid_pairs() -> None:
    provider = FakeSynthProvider(_payload_two_pairs())
    result = synthesize_chunk(
        _chunk(),
        provider=provider,
        qa_style="doctrinal",
        language="es",
        n_pairs=2,
    )
    assert len(result.pairs) == 1


def test_synthesize_chunk_with_judge_loose_keeps_quality_pair() -> None:
    provider = FakeSynthProvider(_payload_two_pairs())
    judge = Judge(
        mode=JudgeMode.LOOSE,
        overrides=JudgeOverrides(),
        llm_provider=None,
        nli_provider=None,
    )
    result = synthesize_chunk(
        _chunk(),
        provider=provider,
        qa_style="doctrinal",
        language="es",
        n_pairs=2,
        judge=judge,
    )
    assert len(result.pairs) == 1
    pair = result.pairs[0]
    assert "judge_score" in pair.metadata
    parsed = json.loads(pair.metadata["judge_score"])
    assert parsed["kept"] is True


def test_synthesize_chunk_with_judge_strict_rejects_no_citation_pair() -> None:
    payload = {
        "pairs": [
            {
                "q": "¿Qué enseña la Biblia sobre el reino?",
                "a": (
                    "El reino de Dios es un gobierno real con Cristo Jesús "
                    "como rey, según Daniel 2:44 y Mateo 6:9-10. "
                    "(Sin código de publicación JW.)"
                ),
            }
        ]
    }
    provider = FakeSynthProvider(payload)
    judge = Judge(
        mode=JudgeMode.STRICT,
        overrides=JudgeOverrides(),
        llm_provider=None,
        nli_provider=None,
    )
    result = synthesize_chunk(
        _chunk(),
        provider=provider,
        qa_style="doctrinal",
        language="es",
        n_pairs=1,
        judge=judge,
    )
    assert result.pairs == []
    assert result.rejected == 1


def test_synthesize_chunk_judge_off_passes_through() -> None:
    provider = FakeSynthProvider(_payload_two_pairs())
    judge = Judge(
        mode=JudgeMode.OFF,
        overrides=JudgeOverrides(),
        llm_provider=None,
        nli_provider=None,
    )
    result = synthesize_chunk(
        _chunk(),
        provider=provider,
        qa_style="doctrinal",
        language="es",
        n_pairs=2,
        judge=judge,
    )
    assert len(result.pairs) == 1
    parsed = json.loads(result.pairs[0].metadata["judge_score"])
    assert parsed["kept"] is True
