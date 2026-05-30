"""GGUF export via Unsloth's `save_pretrained_gguf`.

GGUF is the format consumed by llama.cpp and Ollama. Unsloth accepts:
  * A single quant string ("q4_k_m") → produces one file
  * A list of quants → produces all in a single load (efficient)

We expose both via a single `quants` parameter that accepts str or list.
"""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def _normalize_quant(q: str) -> str:
    """Unsloth accepts e.g. 'q4_k_m' or 'Q4_K_M'; normalize to lowercase."""
    return q.lower().replace("-", "_")


def export_gguf(
    checkpoint_dir: Path,
    output_dir: Path,
    *,
    quant: str | list[str] = "Q4_K_M",
    max_seq_length: int = 2048,
) -> Path:
    """Convert a HF checkpoint to GGUF and return the output directory.

    `quant` accepts either a single quant name or a list. Passing a list
    is significantly more efficient than calling this function multiple
    times because Unsloth holds the model in memory across quant variants.
    """
    from unsloth import FastLanguageModel  # type: ignore[import-untyped]

    output_dir.mkdir(parents=True, exist_ok=True)
    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=str(checkpoint_dir),
        max_seq_length=max_seq_length,
        load_in_4bit=True,
        dtype=None,
    )

    if isinstance(quant, list):
        normalized = [_normalize_quant(q) for q in quant]
        # Unsloth's save_pretrained_gguf signature differs between releases.
        # Newer versions accept `quantization_methods` (plural); older only
        # `quantization_method`. Try the plural first; fall back to a loop.
        try:
            model.save_pretrained_gguf(
                str(output_dir),
                tokenizer,
                quantization_methods=normalized,
            )
        except TypeError:
            for q in normalized:
                model.save_pretrained_gguf(
                    str(output_dir),
                    tokenizer,
                    quantization_method=q,
                )
    else:
        model.save_pretrained_gguf(
            str(output_dir),
            tokenizer,
            quantization_method=_normalize_quant(quant),
        )

    logger.info(
        "GGUF exported to %s (quant=%s)", output_dir, quant
    )
    return output_dir
