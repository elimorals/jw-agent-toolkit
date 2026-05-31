"""JSONL writers for the three training dataset formats we support.

  - raw:        {"text": "...", "metadata": {...}}              → CPT
  - sharegpt:   {"messages": [{role,content}], "metadata": ...}  → SFT
  - alpaca:     {"instruction": ..., "input": "", "output": ...} → SFT alt

We don't pick winners; the trainer reads whichever format the recipe asks
for. ShareGPT is the default for SFT because trl/Unsloth integrate with
it most cleanly via tokenizer chat templates.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path

from jw_rag.chunker import Chunk


@dataclass(frozen=True)
class QAPair:
    """A synthesized Q&A example.

    `source_chunk_id` lets us trace any pair back to its origin chunk, useful
    for debugging mis-generations and for citation provenance later.
    """

    question: str
    answer: str
    source_chunk_id: str
    language: str
    metadata: dict[str, str] = field(default_factory=dict)


def write_raw_jsonl(chunks: Iterable[Chunk], path: Path) -> int:
    """Write `{"text", "metadata"}` records for CPT. Returns row count."""
    path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with path.open("w", encoding="utf-8") as f:
        for c in chunks:
            md = dict(c.metadata)
            md["source_id"] = c.source_id
            f.write(
                json.dumps({"text": c.text, "metadata": md}, ensure_ascii=False)
                + "\n"
            )
            count += 1
    return count


def write_sharegpt_jsonl(qas: Iterable[QAPair], path: Path) -> int:
    """Write ShareGPT-format records for SFT."""
    path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with path.open("w", encoding="utf-8") as f:
        for qa in qas:
            rec = {
                "messages": [
                    {"role": "user", "content": qa.question},
                    {"role": "assistant", "content": qa.answer},
                ],
                "metadata": {
                    "language": qa.language,
                    "source_chunk_id": qa.source_chunk_id,
                    **qa.metadata,
                },
            }
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            count += 1
    return count


def write_alpaca_jsonl(qas: Iterable[QAPair], path: Path) -> int:
    """Write Alpaca-format records (instruction/input/output)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with path.open("w", encoding="utf-8") as f:
        for qa in qas:
            rec = {
                "instruction": qa.question,
                "input": "",
                "output": qa.answer,
                "metadata": {
                    "language": qa.language,
                    "source_chunk_id": qa.source_chunk_id,
                    **qa.metadata,
                },
            }
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            count += 1
    return count
