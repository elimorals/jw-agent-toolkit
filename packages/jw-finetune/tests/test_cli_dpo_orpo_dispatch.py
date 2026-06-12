"""Tests for the CLI `train` dispatch covering dpo/orpo tasks.

We don't actually invoke Unsloth here — that's a GPU-bound dep and not
available in CI. Instead we monkey-patch the trainer entry-points and
assert the CLI routes to the right one based on `recipe.task` and
that it correctly errors out when the preference dataset is missing.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from jw_finetune.cli import app
from jw_finetune.data.models import SourceSpec
from jw_finetune.recipes.base import recipe_to_yaml
from jw_finetune.recipes.presets import get_preset
from typer.testing import CliRunner

runner = CliRunner()


def _write_recipe(tmp_path: Path, preset_name: str) -> Path:
    r = get_preset(preset_name)
    r.sources = [SourceSpec(kind="epub", path="/tmp/x.epub", language="es")]  # type: ignore[arg-type]
    workspace = tmp_path / "ws"
    workspace.mkdir()
    recipe_to_yaml(r, workspace / "recipe.yaml")
    return workspace


def test_train_dpo_errors_when_no_preference_dataset(tmp_path: Path) -> None:
    workspace = _write_recipe(tmp_path, "doctrinal-qa-es-dpo-qwen35")
    result = runner.invoke(app, ["train", "--workspace", str(workspace)])
    assert result.exit_code == 2
    assert "preference_pairs.jsonl" in result.stdout


def test_train_orpo_errors_when_no_preference_dataset(tmp_path: Path) -> None:
    workspace = _write_recipe(tmp_path, "doctrinal-qa-es-orpo-qwen35")
    result = runner.invoke(app, ["train", "--workspace", str(workspace)])
    assert result.exit_code == 2
    assert "preference_pairs.jsonl" in result.stdout


def test_train_dpo_calls_train_dpo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Dispatch goes to train_dpo when dataset present + task=dpo."""
    workspace = _write_recipe(tmp_path, "doctrinal-qa-es-dpo-qwen35")
    (workspace / "preference_pairs.jsonl").write_text("{}\n", encoding="utf-8")

    called: dict[str, Any] = {}

    def fake_train_dpo(rec: Any, dataset: Path, ws: Path, **kw: Any) -> Path:
        called["fn"] = "dpo"
        called["task"] = rec.task
        called["dataset"] = dataset
        return ws / "checkpoints" / "final"

    monkeypatch.setattr("jw_finetune.train.dpo.train_dpo", fake_train_dpo)
    result = runner.invoke(app, ["train", "--workspace", str(workspace)])
    assert result.exit_code == 0, result.stdout
    assert called["fn"] == "dpo"
    assert called["task"] == "dpo"
    assert called["dataset"].name == "preference_pairs.jsonl"


def test_train_orpo_calls_train_orpo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    workspace = _write_recipe(tmp_path, "doctrinal-qa-es-orpo-qwen35")
    (workspace / "preference_pairs.jsonl").write_text("{}\n", encoding="utf-8")

    called: dict[str, Any] = {}

    def fake_train_orpo(rec: Any, dataset: Path, ws: Path, **kw: Any) -> Path:
        called["fn"] = "orpo"
        return ws / "checkpoints" / "final"

    monkeypatch.setattr("jw_finetune.train.orpo.train_orpo", fake_train_orpo)
    result = runner.invoke(app, ["train", "--workspace", str(workspace)])
    assert result.exit_code == 0, result.stdout
    assert called["fn"] == "orpo"


def test_prepare_preference_command_registered() -> None:
    """The new CLI command shows up in --help."""
    result = runner.invoke(app, ["--help"])
    assert "prepare-preference" in result.stdout
