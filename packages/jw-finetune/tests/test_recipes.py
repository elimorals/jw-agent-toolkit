"""Tests for Recipe dataclass, validation, YAML I/O, and preset registry."""

from __future__ import annotations

from pathlib import Path

import pytest
from jw_finetune.data.models import SourceSpec
from jw_finetune.recipes.base import (
    Recipe,
    recipe_from_yaml,
    recipe_to_yaml,
    validate_recipe,
)
from jw_finetune.recipes.presets import PRESETS, get_preset, list_presets


def _valid_recipe(**kw) -> Recipe:
    defaults = dict(
        name="my-recipe",
        task="sft",
        sources=[SourceSpec(kind="jwpub", path="x.jwpub", language="es")],
        languages=["es"],
        publication_kinds=["watchtower"],
        qa_style="doctrinal",
        base_model="unsloth/Qwen2.5-3B-bnb-4bit",
    )
    defaults.update(kw)
    return Recipe(**defaults)


def test_recipe_minimal_valid() -> None:
    r = _valid_recipe()
    assert validate_recipe(r) == []


def test_recipe_sft_requires_qa_style() -> None:
    r = _valid_recipe(qa_style=None)
    errors = validate_recipe(r)
    assert any("qa_style" in e for e in errors)


def test_recipe_empty_sources_error() -> None:
    r = _valid_recipe(sources=[])
    errors = validate_recipe(r)
    assert any("sources" in e for e in errors)


def test_recipe_invalid_lora_rank() -> None:
    r = _valid_recipe(lora_rank=0)
    errors = validate_recipe(r)
    assert any("lora_rank" in e for e in errors)


def test_recipe_invalid_eval_split() -> None:
    r = _valid_recipe(eval_split=0.6)
    errors = validate_recipe(r)
    assert any("eval_split" in e for e in errors)


def test_recipe_yaml_roundtrip(tmp_path: Path) -> None:
    r = _valid_recipe(epochs=3, lora_rank=32)
    p = tmp_path / "r.yaml"
    recipe_to_yaml(r, p)
    r2 = recipe_from_yaml(p)
    assert r2.name == r.name
    assert r2.epochs == 3
    assert r2.lora_rank == 32
    assert len(r2.sources) == 1
    assert r2.sources[0].kind == "jwpub"
    assert r2.sources[0].language == "es"


def test_preset_registry_has_required_presets() -> None:
    expected = {
        "watchtower-style-es-cpt",
        "doctrinal-qa-es-sft",
        "verse-explainer-multilang-sft",
        "apologetics-objections-sft",
    }
    assert expected <= set(PRESETS.keys())


def test_list_presets_sorted() -> None:
    names = list_presets()
    assert names == sorted(names)


def test_get_preset_returns_deep_copy() -> None:
    r1 = get_preset("doctrinal-qa-es-sft")
    r1.languages.append("en")
    r2 = get_preset("doctrinal-qa-es-sft")
    assert r2.languages == ["es"]  # original unchanged


def test_get_preset_unknown_raises() -> None:
    with pytest.raises(KeyError, match="Unknown preset"):
        get_preset("nonexistent-preset")


def test_each_preset_is_valid_after_source_fill() -> None:
    """Every preset must pass validation once user fills `sources`."""
    for name in list_presets():
        r = get_preset(name)
        r.sources = [SourceSpec(kind="jwpub", path="x.jwpub", language=r.languages[0])]
        errors = validate_recipe(r)
        assert errors == [], f"{name}: {errors}"
