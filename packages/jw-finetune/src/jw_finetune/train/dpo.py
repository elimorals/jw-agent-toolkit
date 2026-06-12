"""DPO training via Unsloth + trl.DPOTrainer.

DPO (Direct Preference Optimization) optimizes a policy directly against
pairs `(prompt, chosen, rejected)` using a log-σ objective, with no
reward model and no PPO loop. It needs:

  * A base model (typically a SFT-tuned LoRA checkpoint, but any
    instruction-tuned model works — DPO is a refinement step).
  * A preference dataset in the format `trl.DPOTrainer` expects:
        {"prompt": str, "chosen": str, "rejected": str}
    Our `jw_finetune.synth.preference.build_preference_dataset` writes
    this format directly.

Why use Unsloth here too: same LoRA setup as SFT, no need to keep two
parallel adapter shapes. The reference model is auto-handled by trl
(uses the base policy as reference; with LoRA, the merged base is the
reference, so memory cost stays close to LoRA SFT).

This module is GPU-bound; lazy-imports Unsloth + trl.
"""

from __future__ import annotations

import logging
from pathlib import Path

from jw_finetune.recipes.base import Recipe
from jw_finetune.train.callback import JWMonitorCallback

logger = logging.getLogger(__name__)


def train_dpo(
    recipe: Recipe,
    dataset_path: Path,
    workspace: Path,
    *,
    eval_dataset_path: Path | None = None,
    resume_from_checkpoint: str | bool | None = None,
    beta: float = 0.1,
) -> Path:
    """Run DPO training. Returns final checkpoint path.

    `beta` is the standard DPO temperature (recommended 0.1–0.3). Lower
    beta = more conservative (closer to the reference). For doctrinal
    fine-tunes we default to 0.1 because the reference (SFT'd model)
    already encodes JW voice, and we don't want DPO to drift it.
    """

    if not dataset_path.exists():
        raise FileNotFoundError(dataset_path)

    from datasets import load_dataset  # type: ignore[import-untyped]
    from trl import DPOConfig, DPOTrainer  # type: ignore[import-untyped]
    from unsloth import FastLanguageModel  # type: ignore[import-untyped]
    from unsloth.chat_templates import get_chat_template  # type: ignore[import-untyped]

    workspace.mkdir(parents=True, exist_ok=True)
    ckpt_dir = workspace / "checkpoints"

    # Load model + tokenizer via Unsloth and align the chat template
    # exactly like SFT does. Skipping this is the #1 source of silently
    # wrong DPO runs (chosen/rejected tokens get encoded with a
    # mismatched template and the loss becomes garbage).
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

    args = DPOConfig(
        output_dir=str(ckpt_dir),
        num_train_epochs=recipe.epochs,
        per_device_train_batch_size=recipe.batch_size,
        gradient_accumulation_steps=recipe.gradient_accumulation,
        learning_rate=recipe.learning_rate,
        warmup_ratio=recipe.warmup_ratio,
        weight_decay=recipe.weight_decay,
        # DPO-specific: shorter sequences are typical for preference data
        # because chosen/rejected usually fit within a single SFT response.
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

    # trl.DPOTrainer signature: passing ref_model=None makes trl use the
    # active policy snapshot as reference — correct when using LoRA on
    # top of a frozen base, because the base IS the reference.
    trainer = DPOTrainer(
        model=model,
        ref_model=None,
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
    logger.info("DPO complete: %s", final)
    return final
