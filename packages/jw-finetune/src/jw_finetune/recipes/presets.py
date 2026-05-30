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
        lora_rank=8,    # small dataset → small rank
        lora_alpha=16,
        max_seq_len=2048,
        epochs=3,
        learning_rate=1e-4,
        synth_provider=None,  # extracted from backup
    ),
}


def list_presets() -> list[str]:
    """Return preset names sorted alphabetically."""
    return sorted(PRESETS.keys())


def get_preset(name: str) -> Recipe:
    """Return a deep copy of the preset so the caller can mutate freely."""
    if name not in PRESETS:
        raise KeyError(
            f"Unknown preset: {name!r}. Available: {list_presets()}"
        )
    return deepcopy(PRESETS[name])
