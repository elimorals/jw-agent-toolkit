"""Embedding-similarity evaluation against a curated gold set.

Given a list of (prompt, gold_answer) pairs, this module:
  1. Generates an answer with the trained model for each prompt.
  2. Embeds both gold and generated answers using `jw_rag.embed.Embedder`.
  3. Computes cosine similarity, returns mean and per-prompt scores.

This evaluates CONTENT (does the answer say roughly the same thing as the
gold?), not FORM (refs / terminology). Combined with the form scores in
`refs.py` and `doctrinal.py` you get a richer picture of model quality.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class SimilarityResult:
    n_prompts: int
    mean_similarity: float
    per_prompt: list[dict] = field(default_factory=list)


def _cosine(a: list[float] | Any, b: list[float] | Any) -> float:
    """Cosine similarity for two equally-sized float vectors."""
    import math

    dot = sum(x * y for x, y in zip(a, b, strict=True))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def load_gold_set(path: Path | str) -> list[tuple[str, str]]:
    """Load a JSONL gold set where each line is {"prompt": "...", "answer": "..."}.

    Returns a list of (prompt, gold_answer) tuples.
    """
    out: list[tuple[str, str]] = []
    p = Path(path)
    with p.open("r", encoding="utf-8") as f:
        for ln in f:
            ln = ln.strip()
            if not ln:
                continue
            try:
                obj = json.loads(ln)
            except json.JSONDecodeError:
                continue
            prompt = obj.get("prompt") or obj.get("question")
            gold = obj.get("answer") or obj.get("gold")
            if prompt and gold:
                out.append((str(prompt), str(gold)))
    return out


def evaluate_similarity(
    gold_pairs: list[tuple[str, str]],
    *,
    generate_fn: Callable[[str], str],
    embedder: Any,
) -> SimilarityResult:
    """Run `generate_fn(prompt)` for each prompt and score vs. gold.

    `embedder` must expose `embed(texts: list[str]) -> list[list[float]]`
    matching `jw_rag.embed.Embedder` Protocol. Pass `FakeEmbedder` for
    smoke tests and a real `SentenceTransformerEmbedder` for production.
    """
    if not gold_pairs:
        return SimilarityResult(n_prompts=0, mean_similarity=0.0)

    prompts = [p for p, _ in gold_pairs]
    golds = [g for _, g in gold_pairs]

    answers: list[str] = []
    for p in prompts:
        try:
            answers.append(generate_fn(p))
        except Exception as e:  # noqa: BLE001
            logger.warning("generate_fn failed for prompt %r: %s", p[:50], e)
            answers.append("")

    # Batch embed both sides for efficiency.
    gold_vecs = embedder.embed(golds)
    answer_vecs = embedder.embed(answers)

    per_prompt: list[dict] = []
    total = 0.0
    for prompt, gold, answer, gvec, avec in zip(
        prompts,
        golds,
        answers,
        gold_vecs,
        answer_vecs,
        strict=True,
    ):
        sim = _cosine(gvec, avec)
        per_prompt.append(
            {
                "prompt": prompt,
                "gold": gold,
                "answer": answer,
                "similarity": sim,
            }
        )
        total += sim

    return SimilarityResult(
        n_prompts=len(gold_pairs),
        mean_similarity=total / len(gold_pairs),
        per_prompt=per_prompt,
    )


from typing import Any  # noqa: E402  (used in type hints above)
