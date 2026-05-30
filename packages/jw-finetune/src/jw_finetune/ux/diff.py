"""Compare two checkpoints by running the same prompts through each.

Returns side-by-side answers plus delta scores for citation/terminology.
The Studio UI can render this as a 2-column table; CLI prints it linearly.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class CheckpointDiffRow:
    prompt: str
    answer_a: str
    answer_b: str
    citation_a: float
    citation_b: float
    terminology_a: float
    terminology_b: float


@dataclass
class CheckpointDiffResult:
    checkpoint_a: str
    checkpoint_b: str
    rows: list[CheckpointDiffRow] = field(default_factory=list)
    mean_citation_a: float = 0.0
    mean_citation_b: float = 0.0
    mean_terminology_a: float = 0.0
    mean_terminology_b: float = 0.0


def compare_checkpoints(
    checkpoint_a: Path,
    checkpoint_b: Path,
    prompts: list[str],
    *,
    language: str = "es",
    generate_fn: Any | None = None,
) -> CheckpointDiffResult:
    """Run `prompts` through both checkpoints and return a diff result.

    `generate_fn` (optional) accepts (checkpoint_path, prompt) and returns
    an answer string. If omitted, uses `jw_finetune.eval.runner.run_eval`
    (which requires the GPU stack). Passing a fake generator is the easy
    path for tests.
    """
    from jw_finetune.eval.doctrinal import score_terminology
    from jw_finetune.eval.refs import score_citation_accuracy

    if generate_fn is None:
        def _default_generate(ckpt: Path, prompt: str) -> str:
            from jw_finetune.eval.runner import run_eval
            return run_eval(ckpt, [prompt], language=language).answers[0]
        generate_fn = _default_generate

    rows: list[CheckpointDiffRow] = []
    for prompt in prompts:
        ans_a = generate_fn(checkpoint_a, prompt)
        ans_b = generate_fn(checkpoint_b, prompt)
        rows.append(CheckpointDiffRow(
            prompt=prompt,
            answer_a=ans_a,
            answer_b=ans_b,
            citation_a=score_citation_accuracy([ans_a]),
            citation_b=score_citation_accuracy([ans_b]),
            terminology_a=score_terminology([ans_a], language=language),
            terminology_b=score_terminology([ans_b], language=language),
        ))

    n = max(1, len(rows))
    return CheckpointDiffResult(
        checkpoint_a=str(checkpoint_a),
        checkpoint_b=str(checkpoint_b),
        rows=rows,
        mean_citation_a=sum(r.citation_a for r in rows) / n,
        mean_citation_b=sum(r.citation_b for r in rows) / n,
        mean_terminology_a=sum(r.terminology_a for r in rows) / n,
        mean_terminology_b=sum(r.terminology_b for r in rows) / n,
    )
