"""Tests for JSONL dataset format writers."""

from __future__ import annotations

import json
from pathlib import Path

from jw_rag.chunker import Chunk

from jw_finetune.data.formats import (
    QAPair,
    write_alpaca_jsonl,
    write_raw_jsonl,
    write_sharegpt_jsonl,
)


def test_write_raw_jsonl(tmp_path: Path) -> None:
    chunks = [
        Chunk(id="x:0", text="hola mundo", source_id="x",
              metadata={"language": "es"}),
        Chunk(id="x:1", text="otra cosa", source_id="x",
              metadata={"language": "es"}),
    ]
    out = tmp_path / "raw.jsonl"
    n = write_raw_jsonl(chunks, out)
    assert n == 2
    lines = out.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2
    first = json.loads(lines[0])
    assert first["text"] == "hola mundo"
    assert first["metadata"]["language"] == "es"
    assert first["metadata"]["source_id"] == "x"


def test_write_sharegpt_jsonl(tmp_path: Path) -> None:
    qas = [
        QAPair(
            question="¿Qué es el Reino?",
            answer="El Reino es el gobierno celestial de Dios mencionado en Daniel.",
            source_chunk_id="w24:1#0",
            language="es",
            metadata={"pub_code": "w24"},
        ),
    ]
    out = tmp_path / "sft.jsonl"
    n = write_sharegpt_jsonl(qas, out)
    assert n == 1
    rec = json.loads(out.read_text(encoding="utf-8").strip())
    assert rec["messages"][0]["role"] == "user"
    assert rec["messages"][0]["content"] == "¿Qué es el Reino?"
    assert rec["messages"][1]["role"] == "assistant"
    assert rec["metadata"]["language"] == "es"
    assert rec["metadata"]["pub_code"] == "w24"


def test_write_alpaca_jsonl(tmp_path: Path) -> None:
    qas = [
        QAPair(
            question="What is the Kingdom?",
            answer="The Kingdom is God's heavenly government.",
            source_chunk_id="w24-e:1#0",
            language="en",
        ),
    ]
    out = tmp_path / "alpaca.jsonl"
    n = write_alpaca_jsonl(qas, out)
    assert n == 1
    rec = json.loads(out.read_text(encoding="utf-8").strip())
    assert rec["instruction"] == "What is the Kingdom?"
    assert rec["output"] == "The Kingdom is God's heavenly government."
    assert rec["input"] == ""


def test_write_creates_parent_dir(tmp_path: Path) -> None:
    out = tmp_path / "nested" / "dir" / "raw.jsonl"
    n = write_raw_jsonl(
        [Chunk(id="x:0", text="t", source_id="x", metadata={})], out
    )
    assert n == 1
    assert out.exists()
