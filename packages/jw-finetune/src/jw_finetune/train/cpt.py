"""Continued pretraining (CPT) via Unsloth + trl.SFTTrainer.

CPT is "SFT on raw text with no chat formatting" — each `text` field is a
contiguous sequence and the trainer predicts next tokens. Two CPT-specific
recommendations from Unsloth that we honor here:

  * **Train the embedding layer**: include `embed_tokens` and `lm_head` in
    target_modules, with a much lower LR than the LoRA matrices. We use
    `recipe.embedding_learning_rate_ratio * recipe.learning_rate` for this.
  * **Enable packing**: `packing=True` packs many short documents into a
    single sequence for efficiency. We respect `recipe.packing` if set,
    defaulting to True for CPT.
"""

from __future__ import annotations

import logging
from pathlib import Path

from jw_finetune.recipes.base import Recipe
from jw_finetune.train.callback import JWMonitorCallback

logger = logging.getLogger(__name__)


def train_cpt(
    recipe: Recipe,
    dataset_path: Path,
    workspace: Path,
    *,
    resume_from_checkpoint: str | bool | None = None,
) -> Path:
    """Run CPT and return the final checkpoint directory."""
    if not dataset_path.exists():
        raise FileNotFoundError(dataset_path)

    from datasets import load_dataset  # type: ignore[import-untyped]
    from trl import SFTConfig, SFTTrainer  # type: ignore[import-untyped]
    from unsloth import FastLanguageModel  # type: ignore[import-untyped]

    workspace.mkdir(parents=True, exist_ok=True)
    ckpt_dir = workspace / "checkpoints"

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
            "q_proj", "k_proj", "v_proj", "o_proj",
            "gate_proj", "up_proj", "down_proj",
            "embed_tokens", "lm_head",  # CPT trains the embedding layer too
        ],
        bias="none",
        use_gradient_checkpointing="unsloth",
        random_state=recipe.seed,
        use_rslora=recipe.use_rslora,
    )

    ds = load_dataset("json", data_files=str(dataset_path), split="train")

    embedding_lr = recipe.learning_rate * recipe.embedding_learning_rate_ratio
    # Default packing=True for CPT unless the recipe explicitly says False.
    packing = recipe.packing if recipe.packing is not None else True

    args = SFTConfig(
        output_dir=str(ckpt_dir),
        num_train_epochs=recipe.epochs,
        per_device_train_batch_size=recipe.batch_size,
        gradient_accumulation_steps=recipe.gradient_accumulation,
        learning_rate=recipe.learning_rate,
        embedding_learning_rate=embedding_lr,
        warmup_ratio=recipe.warmup_ratio,
        weight_decay=recipe.weight_decay,
        max_seq_length=recipe.max_seq_len,
        packing=packing,
        logging_steps=10,
        save_steps=100,
        save_total_limit=3,
        seed=recipe.seed,
        report_to="none",
        dataset_text_field="text",
    )

    trainer = SFTTrainer(
        model=model,
        tokenizer=tokenizer,
        train_dataset=ds,
        args=args,
        callbacks=[JWMonitorCallback(workspace=workspace)],
    )

    trainer.train(resume_from_checkpoint=resume_from_checkpoint)
    final = ckpt_dir / "final"
    trainer.save_model(str(final))
    tokenizer.save_pretrained(str(final))
    logger.info("CPT complete: %s (embedding_lr=%g)", final, embedding_lr)
    return final
