"""Tests for multi-tenant brain registry + alias resolution."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from jw_brain.cli import brain_app
from jw_brain.multi_tenant import (
    load_registry,
    register_brain,
    resolve_alias,
    save_registry,
)

runner = CliRunner()


def test_save_and_load_registry_roundtrip(tmp_path: Path) -> None:
    reg = tmp_path / "registry.toml"
    save_registry({"jw": Path("/tmp/jw-brain"), "fin": Path("/tmp/fin-brain")}, reg)
    out = load_registry(reg)
    assert out["jw"] == Path("/tmp/jw-brain").resolve()
    assert out["fin"] == Path("/tmp/fin-brain").resolve()


def test_register_brain_appends_and_overwrites(tmp_path: Path) -> None:
    reg = tmp_path / "registry.toml"
    register_brain("jw", Path("/tmp/a"), registry=reg)
    register_brain("fin", Path("/tmp/b"), registry=reg)
    out = load_registry(reg)
    assert set(out.keys()) == {"jw", "fin"}
    register_brain("jw", Path("/tmp/c"), registry=reg)  # overwrite
    out = load_registry(reg)
    assert out["jw"] == Path("/tmp/c").resolve()


def test_load_registry_returns_empty_when_missing(tmp_path: Path) -> None:
    assert load_registry(tmp_path / "nope.toml") == {}


def test_resolve_alias_returns_none_when_unknown(tmp_path: Path) -> None:
    save_registry({"jw": Path("/tmp/a")}, tmp_path / "r.toml")
    # resolve_alias uses default registry path; we only assert the API shape.
    assert resolve_alias("definitely-not-registered") is None


def test_cli_init_auto_registers_and_list_shows_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """End-to-end: init auto-registers under the dir name; list reports it."""

    reg = tmp_path / "registry.toml"
    monkeypatch.setattr("jw_brain.cli.register_brain",
        lambda alias, path: save_registry({**load_registry(reg), alias: path}, reg))
    monkeypatch.setattr("jw_brain.cli.load_registry", lambda: load_registry(reg))

    brain = tmp_path / "my-tj-brain"
    init_result = runner.invoke(brain_app, ["init", "--brain", str(brain)])
    assert init_result.exit_code == 0

    list_result = runner.invoke(brain_app, ["list"])
    assert list_result.exit_code == 0
    data = json.loads(list_result.stdout)
    assert "my-tj-brain" in data
    assert Path(data["my-tj-brain"]).name == "my-tj-brain"


def test_cli_two_brains_dont_contaminate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Two brains side by side: each has its own graph state."""

    monkeypatch.setenv("JW_GEN_PROVIDER", "fake")
    reg = tmp_path / "registry.toml"
    monkeypatch.setattr("jw_brain.cli.register_brain",
        lambda alias, path: save_registry({**load_registry(reg), alias: path}, reg))

    brain_tj = tmp_path / "tj-brain"
    brain_fin = tmp_path / "fin-brain"
    runner.invoke(brain_app, ["init", "--brain", str(brain_tj)])
    runner.invoke(brain_app, ["init", "--brain", str(brain_fin)])

    # Compile a file only into tj
    (brain_tj / "raw" / "inbox" / "note.md").write_text("Reflexion sobre Juan 3:16", encoding="utf-8")
    runner.invoke(brain_app, ["compile", "--brain", str(brain_tj)])

    s_tj = runner.invoke(brain_app, ["status", "--brain", str(brain_tj)])
    s_fin = runner.invoke(brain_app, ["status", "--brain", str(brain_fin)])
    d_tj = json.loads(s_tj.stdout)
    d_fin = json.loads(s_fin.stdout)
    # No node should leak to the other brain
    assert d_fin["graph"]["n_nodes"] == 0
    assert d_fin["raw"]["pending"] == 0


def test_cli_jw_brain_home_env_resolves_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    brain = tmp_path / "envbrain"
    runner.invoke(brain_app, ["init", "--brain", str(brain)])
    monkeypatch.setenv("JW_BRAIN_HOME", str(brain))
    result = runner.invoke(brain_app, ["status"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["brain"] == str(brain.resolve())
