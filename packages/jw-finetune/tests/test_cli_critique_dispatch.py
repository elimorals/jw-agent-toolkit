"""Tests for the CLI `build-critique-dataset` command (F80 Phase 0).

We exercise the full end-to-end flow with a fake provider so no network or
GPU is involved. The principles loader is the real `jw_eval.principles`;
we just want to confirm the CLI reads input, calls the critique, and
writes output in ShareGPT format.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from jw_finetune.cli import app
from jw_finetune.synth.provider import LLMRequest, LLMResponse
from typer.testing import CliRunner

runner = CliRunner()


class _FakeProvider:
    name = "fake"
    model = "fake-1"

    def __init__(self, canned: str = "respuesta revisada") -> None:
        self.canned = canned
        self.calls: list[LLMRequest] = []

    def generate(self, req: LLMRequest) -> LLMResponse:
        self.calls.append(req)
        return LLMResponse(
            text=self.canned,
            provider=self.name,
            model=self.model,
            usage={"input_tokens": 1, "output_tokens": 1},
        )


def _write_sft_dataset(path: Path, rows: list[tuple[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for q, a in rows:
            f.write(
                json.dumps(
                    {
                        "messages": [
                            {"role": "user", "content": q},
                            {"role": "assistant", "content": a},
                        ],
                        "metadata": {
                            "language": "es",
                            "source_chunk_id": "chunk-001",
                        },
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )


def test_critique_dispatch_errors_when_input_missing(tmp_path: Path) -> None:
    workspace = tmp_path / "ws"
    workspace.mkdir()
    result = runner.invoke(
        app,
        [
            "build-critique-dataset",
            "--workspace",
            str(workspace),
            "--synth-provider",
            "ollama",  # avoid recipe lookup
        ],
    )
    assert result.exit_code == 2
    assert "input dataset not found" in result.stdout


def test_critique_dispatch_writes_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace = tmp_path / "ws"
    workspace.mkdir()
    src = workspace / "dataset_qa.jsonl"
    _write_sft_dataset(
        src,
        [
            ("¿Qué dice la Biblia sobre la oración?",
             "Mateo 6:9 enseña a orar."),  # clean
        ],
    )

    fake = _FakeProvider()
    monkeypatch.setattr(
        "jw_finetune.cli._build_provider", lambda *a, **kw: fake
    )

    result = runner.invoke(
        app,
        [
            "build-critique-dataset",
            "--workspace",
            str(workspace),
        ],
    )
    assert result.exit_code == 0, result.stdout
    out = workspace / "dataset_qa_critique.jsonl"
    assert out.exists()
    lines = [json.loads(line) for line in out.read_text().splitlines() if line.strip()]
    assert len(lines) == 1
    assert lines[0]["messages"][1]["content"] == "Mateo 6:9 enseña a orar."
    # No hard principle was hit, so no LLM call
    assert fake.calls == []


def test_critique_dispatch_uses_custom_input_output_paths(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace = tmp_path / "ws"
    workspace.mkdir()
    src = tmp_path / "raw.jsonl"
    dst = tmp_path / "revised.jsonl"
    _write_sft_dataset(
        src,
        [("P?", "Mateo 6:9 enseña a orar.")],
    )

    monkeypatch.setattr(
        "jw_finetune.cli._build_provider", lambda *a, **kw: _FakeProvider()
    )

    result = runner.invoke(
        app,
        [
            "build-critique-dataset",
            "--workspace",
            str(workspace),
            "--input",
            str(src),
            "--output",
            str(dst),
        ],
    )
    assert result.exit_code == 0, result.stdout
    assert dst.exists()
    # Default output path NOT created
    assert not (workspace / "dataset_qa_critique.jsonl").exists()


def test_critique_dispatch_no_principles_flag(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`--no-principles` should short-circuit before any LLM call."""
    workspace = tmp_path / "ws"
    workspace.mkdir()
    src = workspace / "dataset_qa.jsonl"
    _write_sft_dataset(src, [("P?", "A.")])

    fake = _FakeProvider()
    monkeypatch.setattr(
        "jw_finetune.cli._build_provider", lambda *a, **kw: fake
    )

    result = runner.invoke(
        app,
        [
            "build-critique-dataset",
            "--workspace",
            str(workspace),
            "--no-principles",
        ],
    )
    # When principles are explicitly disabled there's nothing to critique
    # against and the LLM should never be called. The command should still
    # produce an output file (passthrough).
    assert result.exit_code == 0, result.stdout
    out = workspace / "dataset_qa_critique.jsonl"
    assert out.exists()
    assert fake.calls == []
