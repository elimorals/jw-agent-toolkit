"""Built-in recipe presets.

Each preset is an opinionated starting point. The user copies one with
`jw-finetune init --preset <name>`, fills in `sources`, and trains.

Naming convention: `<topic>-<lang(s)>-<task>`.
"""

from __future__ import annotations

from copy import deepcopy

from jw_finetune.recipes.base import Recipe

PRESETS: dict[str, Recipe] = {
    "watchtower-style-es-cpt": Recipe(
        name="watchtower-style-es-cpt",
        task="cpt",
        sources=[],
        languages=["es"],
        publication_kinds=["watchtower"],
        qa_style=None,
        base_model="unsloth/Qwen2.5-3B-bnb-4bit",
        lora_rank=32,
        lora_alpha=64,
        max_seq_len=2048,
        epochs=1,
        learning_rate=1e-4,
    ),
    "doctrinal-qa-es-sft": Recipe(
        name="doctrinal-qa-es-sft",
        task="sft",
        sources=[],
        languages=["es"],
        publication_kinds=["watchtower", "book"],
        qa_style="doctrinal",
        base_model="unsloth/Qwen2.5-7B-bnb-4bit",
        lora_rank=16,
        lora_alpha=32,
        max_seq_len=2048,
        epochs=2,
        learning_rate=2e-4,
        qa_per_chunk=3,
    ),
    "verse-explainer-multilang-sft": Recipe(
        name="verse-explainer-multilang-sft",
        task="sft",
        sources=[],
        languages=["es", "en"],
        publication_kinds=["bible", "watchtower", "book"],
        qa_style="verse-explain",
        base_model="unsloth/Qwen2.5-7B-bnb-4bit",
        lora_rank=16,
        lora_alpha=32,
        max_seq_len=3072,
        epochs=2,
        learning_rate=1.5e-4,
        qa_per_chunk=2,
    ),
    "apologetics-objections-sft": Recipe(
        name="apologetics-objections-sft",
        task="sft",
        sources=[],
        languages=["es"],
        publication_kinds=["book", "brochure", "article"],
        qa_style="objection-handling",
        base_model="unsloth/Qwen2.5-7B-bnb-4bit",
        lora_rank=16,
        lora_alpha=32,
        max_seq_len=2048,
        epochs=3,
        learning_rate=1e-4,
        qa_per_chunk=2,
    ),
    "watchtower-questions-es-sft": Recipe(
        # Uses real (paragraph, question) pairs from the Atalaya — no LLM synth.
        # Set `synth_provider=None` to bypass synthesis entirely.
        name="watchtower-questions-es-sft",
        task="sft",
        sources=[],
        languages=["es"],
        publication_kinds=["watchtower"],
        qa_style="doctrinal",
        base_model="unsloth/Qwen2.5-7B-bnb-4bit",
        lora_rank=16,
        lora_alpha=32,
        max_seq_len=2048,
        epochs=2,
        learning_rate=2e-4,
        synth_provider=None,  # extracted pairs only
    ),
    "ministry-school-es-sft": Recipe(
        # Uses workbook assignments parsed from Vida y Ministerio EPUBs.
        name="ministry-school-es-sft",
        task="sft",
        sources=[],
        languages=["es"],
        publication_kinds=["workbook"],
        qa_style="doctrinal",
        base_model="unsloth/Qwen2.5-3B-bnb-4bit",
        lora_rank=16,
        lora_alpha=32,
        max_seq_len=1536,
        epochs=2,
        learning_rate=2e-4,
        synth_provider=None,  # extracted pairs only
    ),
    "personal-study-companion-sft": Recipe(
        # Uses the user's own JW Library notes as the dataset.
        name="personal-study-companion-sft",
        task="sft",
        sources=[],
        languages=["es"],
        publication_kinds=["other"],
        qa_style="doctrinal",
        base_model="unsloth/Qwen2.5-3B-bnb-4bit",
        lora_rank=8,  # small dataset → small rank
        lora_alpha=16,
        max_seq_len=2048,
        epochs=3,
        learning_rate=1e-4,
        synth_provider=None,  # extracted from backup
    ),
    # ---------------------------------------------------------------
    # F79 — DPO / ORPO refinement recipes (Qwen3.5-0.8B baseline).
    #
    # Qwen3.5-0.8B is Apache-2.0, uses ChatML-style tokens (same template
    # bucket as qwen-2.5/qwen-3 in unsloth.chat_templates), and is small
    # enough that DPO/ORPO + LoRA fits in a single 8 GB GPU or M-series.
    # Use these AFTER an SFT pass on the same base model (see
    # `doctrinal-qa-es-sft-qwen35` below) feeding a preference dataset
    # built with `jw_finetune.synth.preference.build_preference_dataset`.
    # ---------------------------------------------------------------
    "doctrinal-qa-es-sft-qwen35": Recipe(
        # SFT stage for the Qwen3.5 pipeline. Run this first; its
        # checkpoint becomes the base for the DPO/ORPO recipes below.
        name="doctrinal-qa-es-sft-qwen35",
        task="sft",
        sources=[],
        languages=["es"],
        publication_kinds=["watchtower", "book"],
        qa_style="doctrinal",
        base_model="Qwen/Qwen3.5-0.8B",
        lora_rank=16,
        lora_alpha=32,
        max_seq_len=4096,
        epochs=2,
        learning_rate=2e-4,
        chat_template="qwen-3",
        qa_per_chunk=3,
    ),
    "doctrinal-qa-es-dpo-qwen35": Recipe(
        # DPO refinement on top of the SFT checkpoint. Feed it the
        # JSONL produced by build_preference_dataset() — schema
        # {prompt, chosen, rejected}.
        name="doctrinal-qa-es-dpo-qwen35",
        task="dpo",
        sources=[],
        languages=["es"],
        publication_kinds=["watchtower", "book"],
        qa_style=None,  # preference dataset already encodes the style
        base_model="Qwen/Qwen3.5-0.8B",
        lora_rank=16,
        lora_alpha=32,
        max_seq_len=4096,
        epochs=1,  # DPO usually needs 1 epoch; more risks overfitting
        learning_rate=5e-6,  # DPO best-practice: ~10x lower than SFT
        warmup_ratio=0.1,
        chat_template="qwen-3",
    ),
    "doctrinal-qa-es-orpo-qwen35": Recipe(
        # ORPO single-stage variant — useful when no SFT step ran
        # (preference dataset directly), or to compare wall-clock cost
        # against the sft→dpo two-stage. Apache-2.0 base; safe to
        # share LoRA weights downstream.
        name="doctrinal-qa-es-orpo-qwen35",
        task="orpo",
        sources=[],
        languages=["es"],
        publication_kinds=["watchtower", "book"],
        qa_style=None,
        base_model="Qwen/Qwen3.5-0.8B",
        lora_rank=16,
        lora_alpha=32,
        max_seq_len=4096,
        epochs=1,
        learning_rate=8e-6,
        warmup_ratio=0.1,
        chat_template="qwen-3",
    ),
}


def list_presets() -> list[str]:
    """Return preset names sorted alphabetically."""
    return sorted(PRESETS.keys())


def get_preset(name: str) -> Recipe:
    """Return a deep copy of the preset so the caller can mutate freely."""
    if name not in PRESETS:
        raise KeyError(f"Unknown preset: {name!r}. Available: {list_presets()}")
    return deepcopy(PRESETS[name])
