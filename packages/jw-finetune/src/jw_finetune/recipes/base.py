"""Recipe dataclass + validation + YAML roundtrip.

A `Recipe` is the user-facing knob set. Every JW-specific concept
(publication kinds, qa style, language mix) lives here. Internally the
trainer translates these into Unsloth/SFTConfig parameters.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Literal

from jw_finetune.data.models import PublicationKind, SourceSpec

Task = Literal["cpt", "sft", "grpo", "dpo", "orpo"]
QAStyle = Literal["doctrinal", "verse-explain", "objection-handling"]
SynthProvider = Literal["anthropic", "ollama"]


@dataclass
class Recipe:
    """A JW-domain recipe that translates to an Unsloth training config."""

    name: str
    task: Task
    sources: list[SourceSpec]
    languages: list[str]
    publication_kinds: list[PublicationKind]
    qa_style: QAStyle | None
    base_model: str

    # Training hyperparams (Unsloth/trl).
    lora_rank: int = 16
    lora_alpha: int = 32
    lora_dropout: float = 0.0
    max_seq_len: int = 2048
    epochs: int = 1
    batch_size: int = 2
    gradient_accumulation: int = 4
    learning_rate: float = 2e-4
    warmup_ratio: float = 0.05
    weight_decay: float = 0.0
    # Unsloth-specific knobs (added F6.2).
    chat_template: str = "chatml"  # "chatml" | "qwen-2.5" | "llama-3" | "gemma" | "phi-4" | "mistral"
    use_rslora: bool = False  # rank-stabilized LoRA — improves stability for rank>=64
    packing: bool | None = None  # None = task default (CPT=True, SFT=False); set to override
    train_on_responses_only: bool = True  # mask user tokens during SFT
    instruction_part: str = ""  # auto-derived from chat_template if empty
    response_part: str = ""  # auto-derived from chat_template if empty
    use_multi_gpu: bool = False  # enable Accelerate multi-GPU
    embedding_learning_rate_ratio: float = 0.1  # CPT: embedding_lr = lr * this

    # Data preparation knobs.
    min_chunk_chars: int = 80
    max_chunk_chars: int = 1500
    dedupe_threshold: int = 4
    synth_provider: SynthProvider | None = "ollama"
    synth_model: str | None = None
    qa_per_chunk: int = 3
    eval_split: float = 0.05

    # Output / misc.
    output_dir: str = "./jw-finetune-workspace"
    seed: int = 42
    extra: dict[str, str] = field(default_factory=dict)


def validate_recipe(r: Recipe) -> list[str]:
    """Return a list of human-readable validation errors; empty list = valid."""
    errors: list[str] = []
    if not r.name or not r.name.strip():
        errors.append("name: must be non-empty")
    if r.task not in ("cpt", "sft", "grpo", "dpo", "orpo"):
        errors.append(f"task: must be one of cpt/sft/grpo/dpo/orpo, got {r.task!r}")
    if r.task == "sft" and r.qa_style is None:
        errors.append("qa_style: required when task='sft'")
    if not r.sources:
        errors.append("sources: at least one SourceSpec required")
    if not r.languages:
        errors.append("languages: at least one language required")
    if not (1 <= r.lora_rank <= 256):
        errors.append("lora_rank: must be in [1, 256]")
    if r.lora_alpha < 1:
        errors.append("lora_alpha: must be >= 1")
    if not (0.0 <= r.lora_dropout <= 0.5):
        errors.append("lora_dropout: must be in [0.0, 0.5]")
    if r.epochs < 1:
        errors.append("epochs: must be >= 1")
    if r.batch_size < 1:
        errors.append("batch_size: must be >= 1")
    if r.max_seq_len < 128:
        errors.append("max_seq_len: must be >= 128")
    if not (0 <= r.eval_split < 0.5):
        errors.append("eval_split: must be in [0, 0.5)")
    return errors


def recipe_to_yaml(recipe: Recipe, path: Path) -> None:
    """Serialize recipe to YAML."""
    import yaml  # type: ignore[import-untyped]

    d = asdict(recipe)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(d, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )


def recipe_from_yaml(path: Path) -> Recipe:
    """Load a Recipe from YAML, reconstructing nested SourceSpec objects."""
    import yaml  # type: ignore[import-untyped]

    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    raw["sources"] = [SourceSpec(**s) for s in raw.get("sources", [])]
    return Recipe(**raw)
