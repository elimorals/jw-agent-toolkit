"""CLI tests using Typer's CliRunner."""

from __future__ import annotations

from pathlib import Path

import yaml  # type: ignore[import-untyped]
from jw_finetune.cli import app
from typer.testing import CliRunner

runner = CliRunner()


def test_help_runs() -> None:
    r = runner.invoke(app, ["--help"])
    assert r.exit_code == 0
    assert "jw-finetune" in r.stdout


def test_presets_command() -> None:
    """The table may truncate names; check partial matches that survive truncation."""
    r = runner.invoke(app, ["presets"])
    assert r.exit_code == 0
    assert "presets" in r.stdout.lower()
    assert "doctrinal-qa" in r.stdout
    assert "watchtower-style" in r.stdout
    assert "apologetics" in r.stdout
    assert "verse-explainer" in r.stdout


def test_init_writes_yaml(tmp_path: Path) -> None:
    out = tmp_path / "r.yaml"
    r = runner.invoke(app, ["init", "--preset", "doctrinal-qa-es-sft", "--out", str(out)])
    assert r.exit_code == 0, r.stdout
    assert out.exists()
    parsed = yaml.safe_load(out.read_text(encoding="utf-8"))
    assert parsed["name"] == "doctrinal-qa-es-sft"
    assert parsed["task"] == "sft"


def test_init_unknown_preset_fails(tmp_path: Path) -> None:
    out = tmp_path / "r.yaml"
    r = runner.invoke(app, ["init", "--preset", "nonexistent", "--out", str(out)])
    assert r.exit_code != 0


def test_prepare_without_args_fails() -> None:
    r = runner.invoke(app, ["prepare"])
    assert r.exit_code != 0


def test_prepare_without_source_fails(tmp_path: Path) -> None:
    r = runner.invoke(
        app,
        [
            "prepare",
            "--recipe",
            "doctrinal-qa-es-sft",
            "--workspace",
            str(tmp_path),
        ],
    )
    assert r.exit_code != 0


def test_train_missing_recipe_fails(tmp_path: Path) -> None:
    r = runner.invoke(app, ["train", "--workspace", str(tmp_path)])
    assert r.exit_code != 0
    assert "recipe.yaml" in r.stdout or "recipe.yaml" in (r.stderr or "")


def test_export_unknown_format_fails(tmp_path: Path) -> None:
    ckpt = tmp_path / "ckpt"
    ckpt.mkdir()
    r = runner.invoke(
        app,
        [
            "export",
            "--checkpoint",
            str(ckpt),
            "--format",
            "weird-format",
            "--out",
            str(tmp_path / "out"),
        ],
    )
    assert r.exit_code != 0
