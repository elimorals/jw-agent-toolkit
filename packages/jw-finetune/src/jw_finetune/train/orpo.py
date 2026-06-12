"""ORPO training via Unsloth + trl.ORPOTrainer.

ORPO (Odds Ratio Preference Optimization) fuses SFT and preference
learning into a single pass without a reference model. Two practical
consequences:

  1. Cheaper than DPO in memory: no separate reference model to keep
     around. With Unsloth LoRA + 4-bit, ORPO of a 7B model fits in a
     single 24 GB consumer GPU; DPO of the same model requires careful
     gradient checkpointing or it OOMs.
  2. Doesn't need a pre-existing SFT step — but it CAN follow one.
     For doctrinal fine-tunes we recommend `sft → orpo` over
     `orpo from base` because the SFT step instills JW voice and the
     ORPO step refines fidelity.

This module is GPU-bound; lazy-imports Unsloth + trl.
"""

from __future__ import annotations

import logging
from pathlib import Path

from jw_finetune.recipes.base import Recipe
from jw_finetune.train.callback import JWMonitorCallback

logger = logging.getLogger(__name__)


def train_orpo(
    recipe: Recipe,
    dataset_path: Path,
    workspace: Path,
    *,
    eval_dataset_path: Path | None = None,
    resume_from_checkpoint: str | bool | None = None,
    beta: float = 0.1,
) -> Path:
    """Run ORPO training. Returns final checkpoint path.

    Dataset format is the same as DPO: JSONL with `{prompt, chosen,
    rejected}`. `beta` (here, the odds-ratio loss weight λ) defaults to
    0.1 per the ORPO paper recommendation for small-to-medium models.
    """

    if not dataset_path.exists():
        raise FileNotFoundError(dataset_path)

    from datasets import load_dataset  # type: ignore[import-untyped]
    from trl import ORPOConfig, ORPOTrainer  # type: ignore[import-untyped]
    from unsloth import FastLanguageModel  # type: ignore[import-untyped]
    from unsloth.chat_templates import get_chat_template  # type: ignore[import-untyped]

    workspace.mkdir(parents=True, exist_ok=True)
    ckpt_dir = workspace / "checkpoints"

    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=recipe.base_model,
        max_seq_length=recipe.max_seq_len,
        load_in_4bit="bnb-4bit" in recipe.base_model,
        dtype=None,
    )
    tokenizer = get_chat_template(tokenizer, chat_template=recipe.chat_template)

    model = FastLanguageModel.get_peft_model(
        model,
        r=recipe.lora_rank,
        lora_alpha=recipe.lora_alpha,
        lora_dropout=recipe.lora_dropout,
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
        use_rslora=recipe.use_rslora,
    )

    train_ds = load_dataset("json", data_files=str(dataset_path), split="train")
    eval_ds = None
    if eval_dataset_path and eval_dataset_path.exists():
        eval_ds = load_dataset("json", data_files=str(eval_dataset_path), split="train")

    args = ORPOConfig(
        output_dir=str(ckpt_dir),
        num_train_epochs=recipe.epochs,
        per_device_train_batch_size=recipe.batch_size,
        gradient_accumulation_steps=recipe.gradient_accumulation,
        learning_rate=recipe.learning_rate,
        warmup_ratio=recipe.warmup_ratio,
        weight_decay=recipe.weight_decay,
        max_length=recipe.max_seq_len,
        max_prompt_length=min(recipe.max_seq_len // 2, 1024),
        beta=beta,
        logging_steps=10,
        save_steps=100,
        save_total_limit=3,
        seed=recipe.seed,
        report_to="none",
        eval_strategy="steps" if eval_ds else "no",
        eval_steps=100 if eval_ds else None,
    )

    trainer = ORPOTrainer(
        model=model,
        args=args,
        train_dataset=train_ds,
        eval_dataset=eval_ds,
        processing_class=tokenizer,
        callbacks=[JWMonitorCallback(workspace=workspace)],
    )

    trainer.train(resume_from_checkpoint=resume_from_checkpoint)
    final = ckpt_dir / "final"
    trainer.save_model(str(final))
    tokenizer.save_pretrained(str(final))
    logger.info("ORPO complete: %s", final)
    return final
