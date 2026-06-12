"""RLAIF preference-pair dataset builder.

Inputs:
  * A list of `(prompt, source_chunk_id)` items — one per training example.
  * An LLM provider that the `Judge` is comfortable scoring (Anthropic /
    Ollama / OpenAI via the existing `LLMProvider` protocol).
  * A configured `Judge` (mode + nli_provider + principles) that returns
    pairwise verdicts via `score_pair()`.

Output:
  JSONL file with one record per kept preference pair, in the format
  `trl.DPOTrainer` and `trl.ORPOTrainer` accept:

      {"prompt": str, "chosen": str, "rejected": str, "metadata": {...}}

For each prompt we draw `n_candidates` completions at different
temperatures (deterministic temperature sweep — easier to reproduce than
random sampling at fixed temperature). We then run all O(n²) judge
comparisons; pairs that the judge marks as TIE are dropped, and pairs
with `margin < min_margin` are dropped. Cheap and avoids polluting the
DPO dataset with near-identical answers.

Designed for offline / batch use. No async — preference generation is
typically a once-per-corpus job that runs overnight.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from itertools import combinations
from pathlib import Path
from typing import TYPE_CHECKING

from jw_finetune.synth.judge.judge import Judge
from jw_finetune.synth.provider import LLMProvider, LLMRequest

if TYPE_CHECKING:
    from jw_finetune.synth.judge.preference import PreferenceVerdict

logger = logging.getLogger(__name__)


# Temperatures used to draw `n_candidates` answers per prompt. Designed so
# that even 2 candidates produce different styles (cold = deterministic
# factual; warm = more discursive). Keeping the list short keeps cost
# proportional to dataset size.
_DEFAULT_TEMPERATURES: list[float] = [0.1, 0.5, 0.8, 1.0]


@dataclass
class PreferenceItem:
    """Input row for preference generation."""

    prompt: str
    source_chunk_id: str
    language: str = "es"
    system: str = "Eres un asistente que responde sobre publicaciones JW con citas verificables."


@dataclass
class PreferenceStats:
    """Counters returned alongside the JSONL path."""

    items_processed: int = 0
    candidates_generated: int = 0
    pairs_attempted: int = 0
    pairs_kept: int = 0
    pairs_tied: int = 0
    pairs_low_margin: int = 0
    provider_errors: int = 0
    by_winner: dict[str, int] = field(default_factory=lambda: {"a": 0, "b": 0, "tie": 0})

    def as_dict(self) -> dict[str, int | dict[str, int]]:
        return {
            "items_processed": self.items_processed,
            "candidates_generated": self.candidates_generated,
            "pairs_attempted": self.pairs_attempted,
            "pairs_kept": self.pairs_kept,
            "pairs_tied": self.pairs_tied,
            "pairs_low_margin": self.pairs_low_margin,
            "provider_errors": self.provider_errors,
            "by_winner": dict(self.by_winner),
        }


def _generate_candidates(
    item: PreferenceItem,
    *,
    provider: LLMProvider,
    n_candidates: int,
    max_tokens: int,
    temperatures: list[float],
) -> list[tuple[str, float]]:
    """Draw `n_candidates` answers for one prompt. Returns [(text, temp), ...].

    Empty/failed generations are skipped; the caller decides whether the
    remaining pool is large enough.
    """

    out: list[tuple[str, float]] = []
    temps = temperatures[:n_candidates] if temperatures else _DEFAULT_TEMPERATURES[:n_candidates]
    if len(temps) < n_candidates:
        # Recycle by adding +0.1 jitter if the user asks for more candidates
        # than we have temperatures defined. Keeps temperatures distinct.
        extra = [round(temps[-1] + 0.1 * (i + 1), 2) for i in range(n_candidates - len(temps))]
        temps = temps + extra
    for t in temps:
        try:
            resp = provider.generate(
                LLMRequest(
                    system=item.system,
                    user=item.prompt,
                    temperature=t,
                    max_tokens=max_tokens,
                )
            )
        except Exception as exc:  # noqa: BLE001
            logger.debug("provider failed at temp=%.2f: %s", t, exc)
            continue
        text = (resp.text or "").strip()
        if not text:
            continue
        out.append((text, t))
    return out


def _verdict_to_pair(
    item: PreferenceItem,
    a_text: str,
    b_text: str,
    a_temp: float,
    b_temp: float,
    verdict: PreferenceVerdict,
) -> dict[str, object]:
    """Convert a winning verdict into the DPO/ORPO record format."""

    if verdict.winner == "a":
        chosen, rejected = a_text, b_text
        chosen_temp, rejected_temp = a_temp, b_temp
    else:
        chosen, rejected = b_text, a_text
        chosen_temp, rejected_temp = b_temp, a_temp
    return {
        "prompt": item.prompt,
        "chosen": chosen,
        "rejected": rejected,
        "metadata": {
            "source_chunk_id": item.source_chunk_id,
            "language": item.language,
            "chosen_temp": chosen_temp,
            "rejected_temp": rejected_temp,
            "margin": round(verdict.margin, 4),
            "score_chosen": round(verdict.score_a if verdict.winner == "a" else verdict.score_b, 3),
            "score_rejected": round(verdict.score_b if verdict.winner == "a" else verdict.score_a, 3),
            "reasons": verdict.reasons,
        },
    }


def build_preference_dataset(
    items: list[PreferenceItem],
    *,
    provider: LLMProvider,
    judge: Judge,
    output_path: Path,
    n_candidates: int = 3,
    max_tokens: int = 1024,
    min_margin: float = 0.3,
    temperatures: list[float] | None = None,
) -> PreferenceStats:
    """Generate candidates, judge them pairwise, write DPO-format JSONL.

    Parameters tuned for the typical doctrinal-qa setup:
      * `n_candidates=3` → 3 comparisons per prompt, decent coverage.
      * `min_margin=0.3` (on 0-10 scale) → drops near-ties; keeps
        confident preferences.
      * `temperatures` defaults to `[0.1, 0.5, 0.8]` truncated.

    Writes ONE record per kept (winner, loser) pair — so a prompt with 3
    candidates and zero ties yields 3 records (n*(n-1)/2). The output
    JSONL is shuffled by neither prompt nor margin; the trainer's data
    loader is expected to shuffle.
    """

    output_path.parent.mkdir(parents=True, exist_ok=True)
    stats = PreferenceStats()
    temps = temperatures or _DEFAULT_TEMPERATURES

    with output_path.open("w", encoding="utf-8") as f:
        for item in items:
            stats.items_processed += 1
            cands = _generate_candidates(
                item,
                provider=provider,
                n_candidates=n_candidates,
                max_tokens=max_tokens,
                temperatures=temps,
            )
            stats.candidates_generated += len(cands)
            if len(cands) < 2:
                stats.provider_errors += 1
                logger.debug("not enough candidates for prompt: %s", item.source_chunk_id)
                continue
            for (text_a, temp_a), (text_b, temp_b) in combinations(cands, 2):
                stats.pairs_attempted += 1
                verdict = judge.score_pair(
                    question=item.prompt,
                    answer_a=text_a,
                    answer_b=text_b,
                    language=item.language,
                )
                stats.by_winner[verdict.winner] += 1
                if verdict.winner == "tie":
                    stats.pairs_tied += 1
                    continue
                if verdict.margin < min_margin:
                    stats.pairs_low_margin += 1
                    continue
                record = _verdict_to_pair(item, text_a, text_b, temp_a, temp_b, verdict)
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
                stats.pairs_kept += 1
    logger.info(
        "preference dataset built at %s — items=%d, kept=%d, tied=%d, low_margin=%d",
        output_path,
        stats.items_processed,
        stats.pairs_kept,
        stats.pairs_tied,
        stats.pairs_low_margin,
    )
    return stats
