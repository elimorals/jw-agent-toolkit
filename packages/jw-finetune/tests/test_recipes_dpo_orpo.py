"""Tests for the DPO/ORPO recipes and YAML roundtrip."""

from __future__ import annotations

from pathlib import Path

from jw_finetune.data.models import SourceSpec
from jw_finetune.recipes.base import recipe_from_yaml, recipe_to_yaml, validate_recipe
from jw_finetune.recipes.presets import get_preset, list_presets


def _fill_sources(name: str) -> object:
    """Copy a preset and add a stub source so validate_recipe doesn't trip on
    the user-fill-in placeholder."""
    r = get_preset(name)
    r.sources = [
        SourceSpec(kind="epub", path="/tmp/example.epub", language="es")  # type: ignore[arg-type]
    ]
    return r


def test_dpo_orpo_presets_registered() -> None:
    names = list_presets()
    assert "doctrinal-qa-es-sft-qwen35" in names
    assert "doctrinal-qa-es-dpo-qwen35" in names
    assert "doctrinal-qa-es-orpo-qwen35" in names


def test_qwen35_recipes_use_qwen3_chat_template() -> None:
    for name in (
        "doctrinal-qa-es-sft-qwen35",
        "doctrinal-qa-es-dpo-qwen35",
        "doctrinal-qa-es-orpo-qwen35",
    ):
        r = get_preset(name)
        assert r.chat_template == "qwen-3"
        assert r.base_model == "Qwen/Qwen3.5-0.8B"


def test_dpo_recipe_validates() -> None:
    r = _fill_sources("doctrinal-qa-es-dpo-qwen35")
    assert validate_recipe(r) == []  # type: ignore[arg-type]
    assert r.task == "dpo"  # type: ignore[attr-defined]
    # DPO uses a much lower LR than SFT.
    assert r.learning_rate < 1e-4  # type: ignore[attr-defined]


def test_orpo_recipe_validates() -> None:
    r = _fill_sources("doctrinal-qa-es-orpo-qwen35")
    assert validate_recipe(r) == []  # type: ignore[arg-type]
    assert r.task == "orpo"  # type: ignore[attr-defined]


def test_task_validation_rejects_unknown() -> None:
    r = get_preset("doctrinal-qa-es-dpo-qwen35")
    r.task = "rlhf-ppo"  # type: ignore[assignment]
    errors = validate_recipe(r)
    assert any("task" in e for e in errors)


def test_dpo_roundtrip_yaml(tmp_path: Path) -> None:
    r = get_preset("doctrinal-qa-es-dpo-qwen35")
    p = tmp_path / "dpo.yaml"
    recipe_to_yaml(r, p)
    loaded = recipe_from_yaml(p)
    assert loaded.name == r.name
    assert loaded.task == "dpo"
    assert loaded.base_model == r.base_model
    assert loaded.chat_template == r.chat_template


def test_orpo_roundtrip_yaml(tmp_path: Path) -> None:
    r = get_preset("doctrinal-qa-es-orpo-qwen35")
    p = tmp_path / "orpo.yaml"
    recipe_to_yaml(r, p)
    loaded = recipe_from_yaml(p)
    assert loaded.task == "orpo"
