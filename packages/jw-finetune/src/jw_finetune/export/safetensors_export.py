"""Export merged 16-bit safetensors (LoRA + base) or adapter-only weights."""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def export_merged(
    checkpoint_dir: Path,
    output_dir: Path,
    *,
    max_seq_length: int = 2048,
) -> Path:
    """Merge LoRA into base and save as 16-bit safetensors."""
    from unsloth import FastLanguageModel  # type: ignore[import-untyped]

    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=str(checkpoint_dir),
        max_seq_length=max_seq_length,
        load_in_4bit=False,
        dtype=None,
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    model.save_pretrained_merged(
        str(output_dir), tokenizer, save_method="merged_16bit"
    )
    logger.info("Merged 16-bit safetensors exported to %s", output_dir)
    return output_dir


def export_adapter_only(
    checkpoint_dir: Path,
    output_dir: Path,
    *,
    max_seq_length: int = 2048,
) -> Path:
    """Save the LoRA adapter weights only (small file, portable)."""
    from unsloth import FastLanguageModel  # type: ignore[import-untyped]

    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=str(checkpoint_dir),
        max_seq_length=max_seq_length,
        load_in_4bit=True,
        dtype=None,
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    model.save_pretrained(str(output_dir))
    tokenizer.save_pretrained(str(output_dir))
    logger.info("Adapter saved to %s", output_dir)
    return output_dir
