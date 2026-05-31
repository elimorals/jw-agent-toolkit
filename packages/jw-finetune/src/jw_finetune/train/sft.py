"""SFT training via Unsloth + trl.SFTTrainer.

Uses three Unsloth helpers that are easy to miss but critical:
  * `get_chat_template(tokenizer, chat_template)` — fixes the tokenizer's
    chat template to match the base model (chatml/qwen/llama-3/gemma/etc.).
    Without this, the model trains on a generic chat template that doesn't
    match what it was pretrained with.
  * `standardize_sharegpt(dataset)` — converts our ShareGPT JSONL into the
    canonical structure trl expects.
  * `train_on_responses_only(trainer, instruction_part, response_part)` —
    masks user/system tokens so the loss is computed ONLY on the assistant
    response. Without this, the model also learns to "echo the prompt."
"""

from __future__ import annotations

import logging
from pathlib import Path

from jw_finetune.recipes.base import Recipe
from jw_finetune.train.callback import JWMonitorCallback

logger = logging.getLogger(__name__)


# Mapping from short chat_template name → (instruction_part, response_part)
# used by train_on_responses_only. Auto-applied when recipe leaves the
# instruction/response fields empty.
_RESPONSES_ONLY_PARTS: dict[str, tuple[str, str]] = {
    "chatml": ("<|im_start|>user\n", "<|im_start|>assistant\n"),
    "qwen-2.5": ("<|im_start|>user\n", "<|im_start|>assistant\n"),
    "qwen-3": ("<|im_start|>user\n", "<|im_start|>assistant\n"),
    "llama-3": ("<|start_header_id|>user<|end_header_id|>\n\n", "<|start_header_id|>assistant<|end_header_id|>\n\n"),
    "llama-3.1": ("<|start_header_id|>user<|end_header_id|>\n\n", "<|start_header_id|>assistant<|end_header_id|>\n\n"),
    "gemma": ("<start_of_turn>user\n", "<start_of_turn>model\n"),
    "gemma-3": ("<start_of_turn>user\n", "<start_of_turn>model\n"),
    "phi-4": ("<|im_start|>user<|im_sep|>", "<|im_start|>assistant<|im_sep|>"),
    "mistral": ("[INST] ", " [/INST]"),
}


def _resolve_responses_only_parts(recipe: Recipe) -> tuple[str, str]:
    """Return (instruction_part, response_part), respecting recipe overrides."""
    if recipe.instruction_part and recipe.response_part:
        return recipe.instruction_part, recipe.response_part
    parts = _RESPONSES_ONLY_PARTS.get(recipe.chat_template)
    if parts is None:
        logger.warning(
            "Unknown chat_template %r — train_on_responses_only disabled. "
            "Set instruction_part/response_part on the Recipe to enable it.",
            recipe.chat_template,
        )
        return "", ""
    return parts


def train_sft(
    recipe: Recipe,
    dataset_path: Path,
    workspace: Path,
    *,
    eval_dataset_path: Path | None = None,
    resume_from_checkpoint: str | bool | None = None,
) -> Path:
    """Run SFT and return the final checkpoint directory.

    Pipeline (F6.2 update):
      1. Load model + tokenizer via Unsloth (4-bit or fp16 per recipe).
      2. Apply `get_chat_template` to align tokenizer with base model.
      3. Apply `get_peft_model` with rsLoRA when recipe.use_rslora.
      4. Load dataset and `standardize_sharegpt` it.
      5. Build SFTTrainer.
      6. Wrap with `train_on_responses_only` if recipe says so.
      7. Train.
    """
    if not dataset_path.exists():
        raise FileNotFoundError(dataset_path)

    from datasets import load_dataset  # type: ignore[import-untyped]
    from trl import SFTConfig, SFTTrainer  # type: ignore[import-untyped]
    from unsloth import FastLanguageModel  # type: ignore[import-untyped]
    from unsloth.chat_templates import (  # type: ignore[import-untyped]
        get_chat_template,
        standardize_sharegpt,
        train_on_responses_only,
    )

    workspace.mkdir(parents=True, exist_ok=True)
    ckpt_dir = workspace / "checkpoints"

    # 1 + 2. Load and template-align.
    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=recipe.base_model,
        max_seq_length=recipe.max_seq_len,
        load_in_4bit="bnb-4bit" in recipe.base_model,
        dtype=None,
    )
    tokenizer = get_chat_template(tokenizer, chat_template=recipe.chat_template)

    # 3. LoRA (with rsLoRA when requested).
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

    # 4. Load + standardize dataset.
    train_ds = load_dataset("json", data_files=str(dataset_path), split="train")
    try:
        train_ds = standardize_sharegpt(train_ds)
    except Exception as e:  # noqa: BLE001
        logger.warning("standardize_sharegpt failed (%s); using raw dataset.", e)

    eval_ds = None
    if eval_dataset_path and eval_dataset_path.exists():
        eval_ds = load_dataset("json", data_files=str(eval_dataset_path), split="train")
        try:
            eval_ds = standardize_sharegpt(eval_ds)
        except Exception:  # noqa: BLE001
            pass

    # 5. SFTTrainer.
    args = SFTConfig(
        output_dir=str(ckpt_dir),
        num_train_epochs=recipe.epochs,
        per_device_train_batch_size=recipe.batch_size,
        gradient_accumulation_steps=recipe.gradient_accumulation,
        learning_rate=recipe.learning_rate,
        warmup_ratio=recipe.warmup_ratio,
        weight_decay=recipe.weight_decay,
        max_seq_length=recipe.max_seq_len,
        packing=recipe.packing if recipe.packing is not None else False,  # SFT default: off
        logging_steps=10,
        save_steps=100,
        save_total_limit=3,
        seed=recipe.seed,
        report_to="none",
        eval_strategy="steps" if eval_ds else "no",
        eval_steps=100 if eval_ds else None,
    )

    trainer = SFTTrainer(
        model=model,
        tokenizer=tokenizer,
        train_dataset=train_ds,
        eval_dataset=eval_ds,
        args=args,
        callbacks=[JWMonitorCallback(workspace=workspace)],
    )

    # 6. Mask user tokens.
    if recipe.train_on_responses_only:
        instruction_part, response_part = _resolve_responses_only_parts(recipe)
        if instruction_part and response_part:
            trainer = train_on_responses_only(
                trainer,
                instruction_part=instruction_part,
                response_part=response_part,
            )

    # 7. Go.
    trainer.train(resume_from_checkpoint=resume_from_checkpoint)
    final = ckpt_dir / "final"
    trainer.save_model(str(final))
    tokenizer.save_pretrained(str(final))
    logger.info("SFT complete: %s", final)
    return final
