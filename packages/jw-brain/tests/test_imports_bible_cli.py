"""F58.9 — Smoke test del comando `jw brain import-bible`.

Sandboxea el registry (precedente `test_multi_tenant.py`) para no
contaminar `~/.jw-brain/registry.toml`, y verifica:

  - `--help` lista el comando.
  - `--periods-only` upsertea los 10 periodos del catálogo curado.
  - `--insight <jwpub> --symbol it --meps-language 0` ejecuta el
    pipeline completo Person/Place/Passage sobre el fixture mini.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from jw_brain.cli import brain_app
from typer.testing import CliRunner

FIXTURE = Path(__file__).parent / "fixtures" / "insight_mini" / "it_mini.jwpub"


@pytest.fixture()
def runner() -> CliRunner:
    return CliRunner()


def test_import_bible_help(runner: CliRunner) -> None:
    result = runner.invoke(brain_app, ["import-bible", "--help"])
    assert result.exit_code == 0
    assert "insight" in result.stdout.lower() or "periods" in result.stdout.lower()


def test_import_bible_periods_only(
    runner: CliRunner,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Sin --insight, importa solo el catálogo de periodos."""

    from jw_brain.multi_tenant import load_registry, save_registry

    reg = tmp_path / "registry.toml"
    monkeypatch.setattr(
        "jw_brain.cli.register_brain",
        lambda alias, path: save_registry({**load_registry(reg), alias: path}, reg),
    )
    monkeypatch.setattr("jw_brain.cli.load_registry", lambda: load_registry(reg))

    brain_home = tmp_path / "brain"
    brain_home.mkdir()
    result = runner.invoke(brain_app, ["init", "--brain", str(brain_home)])
    assert result.exit_code == 0

    result = runner.invoke(
        brain_app,
        ["import-bible", "--brain", str(brain_home), "--periods-only"],
    )
    assert result.exit_code == 0, result.stdout
    assert "10" in result.stdout  # 10 periodos


def test_import_bible_with_insight_jwpub(
    runner: CliRunner,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from jw_brain.multi_tenant import load_registry, save_registry

    reg = tmp_path / "registry.toml"
    monkeypatch.setattr(
        "jw_brain.cli.register_brain",
        lambda alias, path: save_registry({**load_registry(reg), alias: path}, reg),
    )
    monkeypatch.setattr("jw_brain.cli.load_registry", lambda: load_registry(reg))

    brain_home = tmp_path / "brain"
    brain_home.mkdir()
    runner.invoke(brain_app, ["init", "--brain", str(brain_home)])

    result = runner.invoke(
        brain_app,
        [
            "import-bible",
            "--brain",
            str(brain_home),
            "--insight",
            str(FIXTURE),
            "--symbol",
            "it",
            "--meps-language",
            "0",
        ],
    )
    assert result.exit_code == 0, result.stdout
    assert "person" in result.stdout.lower()
    assert "place" in result.stdout.lower()
