"""Recipe wizard logic — collects user inputs into a Recipe.

This module is the *headless* part of the TUI wizard so it can be tested
without spinning up a terminal. The Textual app (`app.py`) just renders
this state machine.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from jw_finetune.data.models import SourceSpec
from jw_finetune.recipes.base import Recipe, validate_recipe
from jw_finetune.recipes.presets import get_preset, list_presets

Step = Literal[
    "choose_preset",
    "name",
    "sources",
    "base_model",
    "hyperparams",
    "synth",
    "review",
    "done",
]


@dataclass
class WizardState:
    """Mutable wizard state. Steps advance through `next_step()`."""

    step: Step = "choose_preset"
    recipe: Recipe | None = None
    errors: list[str] = field(default_factory=list)

    _ORDER: tuple[Step, ...] = (
        "choose_preset",
        "name",
        "sources",
        "base_model",
        "hyperparams",
        "synth",
        "review",
        "done",
    )

    def select_preset(self, preset_name: str) -> None:
        self.recipe = get_preset(preset_name)
        self.errors = []
        self.step = "name"

    def update_name(self, name: str) -> None:
        if self.recipe is not None:
            self.recipe.name = name.strip() or self.recipe.name

    def add_source(self, kind: str, path: str, language: str) -> None:
        if self.recipe is None:
            return
        self.recipe.sources.append(
            SourceSpec(kind=kind, path=path, language=language)  # type: ignore[arg-type]
        )

    def remove_source(self, index: int) -> None:
        if self.recipe is None:
            return
        if 0 <= index < len(self.recipe.sources):
            self.recipe.sources.pop(index)

    def update_base_model(self, model: str) -> None:
        if self.recipe is not None and model.strip():
            self.recipe.base_model = model.strip()

    def update_hyperparams(
        self,
        *,
        epochs: int | None = None,
        lora_rank: int | None = None,
        learning_rate: float | None = None,
        max_seq_len: int | None = None,
        batch_size: int | None = None,
    ) -> None:
        if self.recipe is None:
            return
        if epochs is not None:
            self.recipe.epochs = epochs
        if lora_rank is not None:
            self.recipe.lora_rank = lora_rank
        if learning_rate is not None:
            self.recipe.learning_rate = learning_rate
        if max_seq_len is not None:
            self.recipe.max_seq_len = max_seq_len
        if batch_size is not None:
            self.recipe.batch_size = batch_size

    def update_synth(
        self,
        *,
        provider: str | None = None,
        model: str | None = None,
        qa_per_chunk: int | None = None,
    ) -> None:
        if self.recipe is None:
            return
        if provider is not None:
            self.recipe.synth_provider = provider  # type: ignore[assignment]
        if model is not None:
            self.recipe.synth_model = model
        if qa_per_chunk is not None:
            self.recipe.qa_per_chunk = qa_per_chunk

    def review(self) -> list[str]:
        if self.recipe is None:
            self.errors = ["No recipe selected"]
            return self.errors
        self.errors = validate_recipe(self.recipe)
        return self.errors

    def next_step(self) -> Step:
        idx = self._ORDER.index(self.step)
        if idx + 1 < len(self._ORDER):
            self.step = self._ORDER[idx + 1]
        return self.step

    def prev_step(self) -> Step:
        idx = self._ORDER.index(self.step)
        if idx > 0:
            self.step = self._ORDER[idx - 1]
        return self.step


def available_presets() -> list[str]:
    """Convenience wrapper used by the Textual screen."""
    return list_presets()
