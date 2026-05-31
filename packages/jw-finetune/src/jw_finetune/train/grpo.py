"""GRPO (Group Relative Policy Optimization) via Unsloth + trl.

GRPO is a reinforcement-learning method that uses a reward function instead
of preference pairs (DPO) or a value model (PPO). The user supplies a
function `reward_fn(prompt, completion) -> float` and the trainer optimizes
the model to produce completions that score higher.

For JW use cases, useful reward functions include:
  - `make_citation_reward()` — rewards answers that include valid bible refs
  - `make_terminology_reward()` — rewards answers that use JW-specific vocab
  - Composite: weighted sum of the above

This module is GPU-bound; lazy-imports Unsloth.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path

from jw_finetune.eval.doctrinal import score_terminology
from jw_finetune.eval.refs import score_citation_accuracy
from jw_finetune.recipes.base import Recipe
from jw_finetune.train.callback import JWMonitorCallback

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Reward functions
# ---------------------------------------------------------------------------


def make_citation_reward(expect_at_least: int = 1) -> Callable[[list[str], list[str]], list[float]]:
    """Reward = 1.0 if answer has >= `expect_at_least` bible refs, else 0.0.

    Signature matches trl's GRPOTrainer reward_funcs API:
    `fn(prompts, completions) -> list[float]`.
    """

    def _reward(prompts: list[str], completions: list[str]) -> list[float]:
        return [1.0 if score_citation_accuracy([c], expect_at_least=expect_at_least) > 0 else 0.0 for c in completions]

    _reward.__name__ = f"citation_reward_min{expect_at_least}"
    return _reward


def make_terminology_reward(language: str = "es") -> Callable[[list[str], list[str]], list[float]]:
    """Reward = 1.0 if completion includes >= 1 JW-specific term, else 0.0."""

    def _reward(prompts: list[str], completions: list[str]) -> list[float]:
        return [1.0 if score_terminology([c], language=language) > 0 else 0.0 for c in completions]

    _reward.__name__ = f"terminology_reward_{language}"
    return _reward


def make_length_penalty(min_chars: int = 30, max_chars: int = 1500) -> Callable:
    """Reward = 1.0 if length is in range; linear penalty outside."""

    def _reward(prompts: list[str], completions: list[str]) -> list[float]:
        out = []
        for c in completions:
            n = len(c.strip())
            if min_chars <= n <= max_chars:
                out.append(1.0)
            elif n < min_chars:
                out.append(max(0.0, n / min_chars))
            else:
                # gentle penalty above max
                excess = n - max_chars
                out.append(max(0.0, 1.0 - excess / max_chars))
        return out

    _reward.__name__ = "length_penalty"
    return _reward


def make_apocrypha_penalty(
    min_confidence_genuine: float = 0.4,
) -> Callable[[list[str], list[str]], list[float]]:
    """Reward = 1.0 if NO apocryphal references; 0.0 if any detected.

    Uses `jw_agents.apocrypha_detector` internals to flag mentions of
    apocryphal texts (Tobit, Judith, Sirach, Maccabees, etc.) framed as
    canonical scripture. JW doctrine excludes the apocrypha; this reward
    discourages drift during RL.
    """

    def _reward(prompts: list[str], completions: list[str]) -> list[float]:
        try:
            from jw_agents.apocrypha_detector import (
                _detect_framings,
                _extract_candidates,
                _verdict,
            )
        except ImportError:
            return [1.0] * len(completions)
        out = []
        for c in completions:
            framings = _detect_framings(c)
            if not framings:
                out.append(1.0)
                continue
            candidates = _extract_candidates(c, framings)
            penalized = False
            for cand in candidates:
                verdict = _verdict(cand, min_confidence_genuine=min_confidence_genuine)
                if isinstance(verdict, str) and "apocrypha" in verdict.lower():
                    penalized = True
                    break
            out.append(0.0 if penalized else 1.0)
        return out

    _reward.__name__ = "apocrypha_penalty"
    return _reward


def composite_reward(
    reward_fns: list[Callable],
    weights: list[float] | None = None,
) -> Callable[[list[str], list[str]], list[float]]:
    """Weighted sum of multiple reward functions."""
    if weights is None:
        weights = [1.0] * len(reward_fns)
    if len(weights) != len(reward_fns):
        raise ValueError("len(weights) must equal len(reward_fns)")

    def _reward(prompts: list[str], completions: list[str]) -> list[float]:
        totals = [0.0] * len(completions)
        for fn, w in zip(reward_fns, weights, strict=True):
            scores = fn(prompts, completions)
            for i, s in enumerate(scores):
                totals[i] += w * s
        return totals

    _reward.__name__ = "composite_reward"
    return _reward


# ---------------------------------------------------------------------------
# Trainer
# ---------------------------------------------------------------------------


def train_grpo(
    recipe: Recipe,
    dataset_path: Path,
    workspace: Path,
    *,
    reward_fn: Callable[[list[str], list[str]], list[float]] | None = None,
    resume_from_checkpoint: str | bool | None = None,
) -> Path:
    """Run GRPO training. Returns final checkpoint path.

    The dataset must contain a `prompt` field per record. The trainer
    generates `num_generations` completions per prompt and uses the reward
    function to optimize the policy.

    If `reward_fn` is None, defaults to:
        composite(citation_reward, terminology_reward(recipe.languages[0]),
                  length_penalty)
    """
    if not dataset_path.exists():
        raise FileNotFoundError(dataset_path)

    from datasets import load_dataset  # type: ignore[import-untyped]
    from trl import GRPOConfig, GRPOTrainer  # type: ignore[import-untyped]
    from unsloth import FastLanguageModel  # type: ignore[import-untyped]

    workspace.mkdir(parents=True, exist_ok=True)
    ckpt_dir = workspace / "checkpoints"

    if reward_fn is None:
        lang = recipe.languages[0] if recipe.languages else "es"
        # JW-tuned default weights:
        #  - Citation accuracy is the highest-leverage signal: a JW
        #    answer without scripture support is doctrinally weak. 0.45.
        #  - Terminology second: distinguishes JW voice from generic
        #    Christian. 0.30.
        #  - Length penalty third: keeps answers in the doctrinal
        #    "comment-card length" range (~30-1500 chars). 0.15.
        #  - Apocrypha penalty (new): negative weight to penalize
        #    referring to apocryphal texts as canonical. 0.10 absolute.
        reward_fn = composite_reward(
            [
                make_citation_reward(expect_at_least=1),
                make_terminology_reward(language=lang),
                make_length_penalty(min_chars=30, max_chars=1500),
            ],
            weights=[0.45, 0.30, 0.15],
        )

    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=recipe.base_model,
        max_seq_length=recipe.max_seq_len,
        load_in_4bit="bnb-4bit" in recipe.base_model,
        dtype=None,
    )
    model = FastLanguageModel.get_peft_model(
        model,
        r=recipe.lora_rank,
        lora_alpha=recipe.lora_alpha,
        target_modules=[
            "q_proj",
            "k_proj",
            "v_proj",
            "o_proj",
            "gate_proj",
            "up_proj",
            "down_proj",
        ],
        bias="none",
        use_gradient_checkpointing="unsloth",
        random_state=recipe.seed,
    )

    ds = load_dataset("json", data_files=str(dataset_path), split="train")

    # JW-tuned GRPO settings:
    #   max_completion_length=1024 (doctrinal answers often exceed 512)
    #   num_generations=6 (more samples → smoother reward signal)
    args = GRPOConfig(
        output_dir=str(ckpt_dir),
        num_train_epochs=recipe.epochs,
        per_device_train_batch_size=recipe.batch_size,
        gradient_accumulation_steps=recipe.gradient_accumulation,
        learning_rate=recipe.learning_rate,
        warmup_ratio=recipe.warmup_ratio,
        max_completion_length=1024,
        num_generations=6,
        logging_steps=10,
        save_steps=100,
        save_total_limit=3,
        seed=recipe.seed,
        report_to="none",
    )

    trainer = GRPOTrainer(
        model=model,
        processing_class=tokenizer,
        reward_funcs=[reward_fn],
        args=args,
        train_dataset=ds,
        callbacks=[JWMonitorCallback(workspace=workspace)],
    )

    trainer.train(resume_from_checkpoint=resume_from_checkpoint)
    final = ckpt_dir / "final"
    trainer.save_model(str(final))
    tokenizer.save_pretrained(str(final))
    return final
