"""Eval runner: load a checkpoint, run prompts, score answers.

Lazy-imports Unsloth so the package stays importable without a GPU stack.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path

from jw_finetune.eval.doctrinal import score_terminology
from jw_finetune.eval.refs import score_citation_accuracy

logger = logging.getLogger(__name__)


@dataclass
class EvalResult:
    n_prompts: int
    citation_accuracy: float
    terminology_score: float
    answers: list[str] = field(default_factory=list)


def run_eval(
    checkpoint_dir: Path,
    prompts: list[str],
    *,
    language: str = "es",
    max_new_tokens: int = 256,
    max_seq_length: int = 2048,
) -> EvalResult:
    """Run prompts through the trained model and score the answers."""
    from unsloth import FastLanguageModel  # type: ignore[import-untyped]

    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=str(checkpoint_dir),
        max_seq_length=max_seq_length,
        load_in_4bit=True,
        dtype=None,
    )
    FastLanguageModel.for_inference(model)

    answers: list[str] = []
    for p in prompts:
        inputs = tokenizer.apply_chat_template(
            [{"role": "user", "content": p}],
            return_tensors="pt",
            add_generation_prompt=True,
        ).to(model.device)
        out = model.generate(inputs, max_new_tokens=max_new_tokens, do_sample=False)
        text = tokenizer.decode(out[0][inputs.shape[1] :], skip_special_tokens=True)
        answers.append(text)

    return EvalResult(
        n_prompts=len(prompts),
        citation_accuracy=score_citation_accuracy(answers),
        terminology_score=score_terminology(answers, language=language),
        answers=answers,
    )


def write_eval_report(result: EvalResult, path: Path) -> None:
    """Persist an EvalResult as JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "n_prompts": result.n_prompts,
                "citation_accuracy": result.citation_accuracy,
                "terminology_score": result.terminology_score,
                "answers": result.answers,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
