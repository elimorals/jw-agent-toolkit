"""End-to-end test for the judge plumbing in data extract."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jw_rag.chunker import Chunk

from jw_finetune.data.extract import run_extract_with_judge
from jw_finetune.synth.judge import JudgeMode
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


def _chunks() -> list[Chunk]:
    return [
        Chunk(
            id="c1",
            text="Texto fuente uno.",
            source_id="s1",
            metadata={"pub_code": "w23", "section_ref": "p. 5"},
        ),
        Chunk(
            id="c2",
            text="Texto fuente dos.",
            source_id="s1",
            metadata={"pub_code": "w23", "section_ref": "p. 6"},
        ),
    ]


def _payload() -> dict[str, Any]:
    return {
        "pairs": [
            {
                "q": "¿Qué enseña la Biblia sobre el reino?",
                "a": (
                    "Como muestra w23 p. 5, el reino de Dios es un gobierno "
                    "real con Cristo Jesús como rey, según Daniel 2:44 y "
                    "Mateo 6:9-10."
                ),
            },
        ]
    }


def test_run_extract_with_judge_loose_kept(tmp_path: Path) -> None:
    out_path = tmp_path / "train.jsonl"
    stats = run_extract_with_judge(
        chunks=_chunks(),
        provider=FakeSynthProvider(_payload()),
        qa_style="doctrinal",
        language="es",
        output_path=out_path,
        judge_mode=JudgeMode.LOOSE,
    )
    assert stats.total == 2
    assert stats.kept == 2
    assert stats.rejected == 0
    assert out_path.exists()
    lines = out_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    first = json.loads(lines[0])
    md = first.get("metadata", {})
    assert "judge_score" in md


def test_run_extract_with_judge_strict_rejects_no_citation(
    tmp_path: Path,
) -> None:
    payload = {
        "pairs": [
            {
                "q": "¿Qué enseña la Biblia sobre el reino?",
                "a": (
                    "Es un gobierno real con Cristo Jesús como rey, "
                    "Daniel 2:44 y Mateo 6:9-10."
                ),
            }
        ]
    }
    out_path = tmp_path / "train.jsonl"
    stats = run_extract_with_judge(
        chunks=_chunks(),
        provider=FakeSynthProvider(payload),
        qa_style="doctrinal",
        language="es",
        output_path=out_path,
        judge_mode=JudgeMode.STRICT,
    )
    assert stats.kept == 0
    assert stats.rejected == 2
    assert (
        "no_jw_citation" in stats.rejection_reasons
        or "overall_below_threshold" in stats.rejection_reasons
    )


def test_run_extract_with_judge_off_passes_all(tmp_path: Path) -> None:
    out_path = tmp_path / "train.jsonl"
    stats = run_extract_with_judge(
        chunks=_chunks(),
        provider=FakeSynthProvider(_payload()),
        qa_style="doctrinal",
        language="es",
        output_path=out_path,
        judge_mode=JudgeMode.OFF,
    )
    assert stats.kept == 2
    assert stats.rejected == 0


def test_run_extract_with_judge_dump_rejected(tmp_path: Path) -> None:
    payload = {
        "pairs": [
            {
                "q": "¿Qué enseña la Biblia sobre el reino?",
                "a": (
                    "Es un gobierno real con Cristo Jesús como rey, "
                    "Daniel 2:44."
                ),
            }
        ]
    }
    out_path = tmp_path / "train.jsonl"
    dump_path = tmp_path / "rejected.jsonl"
    run_extract_with_judge(
        chunks=_chunks(),
        provider=FakeSynthProvider(payload),
        qa_style="doctrinal",
        language="es",
        output_path=out_path,
        judge_mode=JudgeMode.STRICT,
        dump_rejected_path=dump_path,
    )
    assert dump_path.exists()
    rejected = [
        json.loads(ln)
        for ln in dump_path.read_text(encoding="utf-8").splitlines()
    ]
    assert len(rejected) >= 1
    assert "judge_score" in rejected[0]
    assert "question" in rejected[0]
