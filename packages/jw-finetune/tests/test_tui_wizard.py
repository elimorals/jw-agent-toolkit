"""Tests for the headless wizard state machine (no Textual required)."""

from __future__ import annotations

from jw_finetune.tui.wizard import WizardState, available_presets


def test_initial_state() -> None:
    s = WizardState()
    assert s.step == "choose_preset"
    assert s.recipe is None
    assert s.errors == []


def test_select_preset_advances_to_name_step() -> None:
    s = WizardState()
    s.select_preset("doctrinal-qa-es-sft")
    assert s.recipe is not None
    assert s.recipe.name == "doctrinal-qa-es-sft"
    assert s.step == "name"


def test_next_step_walks_through_order() -> None:
    s = WizardState()
    s.select_preset("doctrinal-qa-es-sft")
    expected = ("sources", "base_model", "hyperparams", "synth", "review", "done", "done")
    seen = tuple(s.next_step() for _ in expected)
    assert seen == expected


def test_prev_step_does_not_underflow() -> None:
    s = WizardState()
    for _ in range(10):
        s.prev_step()
    assert s.step == "choose_preset"


def test_update_name() -> None:
    s = WizardState()
    s.select_preset("doctrinal-qa-es-sft")
    s.update_name("my-custom-recipe")
    assert s.recipe is not None
    assert s.recipe.name == "my-custom-recipe"


def test_update_hyperparams() -> None:
    s = WizardState()
    s.select_preset("doctrinal-qa-es-sft")
    s.update_hyperparams(epochs=5, lora_rank=64, learning_rate=1e-4)
    assert s.recipe is not None
    assert s.recipe.epochs == 5
    assert s.recipe.lora_rank == 64
    assert s.recipe.learning_rate == 1e-4


def test_add_and_remove_source() -> None:
    s = WizardState()
    s.select_preset("doctrinal-qa-es-sft")
    s.add_source("jwpub", "/path/a.jwpub", "es")
    s.add_source("epub", "/path/b.epub", "es")
    assert s.recipe is not None
    assert len(s.recipe.sources) == 2
    s.remove_source(0)
    assert len(s.recipe.sources) == 1
    assert s.recipe.sources[0].kind == "epub"


def test_review_returns_errors_for_empty_sources() -> None:
    s = WizardState()
    s.select_preset("doctrinal-qa-es-sft")
    errors = s.review()
    assert any("sources" in e for e in errors)


def test_review_returns_empty_when_valid() -> None:
    s = WizardState()
    s.select_preset("doctrinal-qa-es-sft")
    s.add_source("jwpub", "/p.jwpub", "es")
    errors = s.review()
    assert errors == []


def test_available_presets_returns_known_names() -> None:
    names = available_presets()
    assert "doctrinal-qa-es-sft" in names
    assert "watchtower-style-es-cpt" in names


def test_update_synth() -> None:
    s = WizardState()
    s.select_preset("doctrinal-qa-es-sft")
    s.update_synth(provider="anthropic", model="claude-haiku", qa_per_chunk=5)
    assert s.recipe is not None
    assert s.recipe.synth_provider == "anthropic"
    assert s.recipe.synth_model == "claude-haiku"
    assert s.recipe.qa_per_chunk == 5
