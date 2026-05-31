"""Tests for the `jw grep` CLI command."""

from __future__ import annotations

from pathlib import Path

from jw_cli.main import app
from typer.testing import CliRunner

from tests.fixtures.concordance import build_minimal_epub  # type: ignore[import-not-found]

runner = CliRunner()


def test_grep_build_index_then_search(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("JW_CONCORDANCE_DB", str(tmp_path / "c.db"))
    epub = build_minimal_epub(
        tmp_path / "demo.epub",
        title="Demo",
        paragraphs=["the quick brown fox jumps over the lazy dog"],
    )
    r1 = runner.invoke(app, ["grep", "--build-index", str(epub), "--language", "en"])
    assert r1.exit_code == 0, r1.stdout
    assert "Indexed" in r1.stdout or "inserted" in r1.stdout.lower()

    r2 = runner.invoke(app, ["grep", "brown fox", "--language", "en"])
    assert r2.exit_code == 0, r2.stdout
    assert "‹brown fox›" in r2.stdout or "brown fox" in r2.stdout


def test_grep_stats(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("JW_CONCORDANCE_DB", str(tmp_path / "c.db"))
    r = runner.invoke(app, ["grep", "--stats"])
    assert r.exit_code == 0
    assert "total" in r.stdout.lower() or "empty" in r.stdout.lower()


def test_grep_rejects_regex(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("JW_CONCORDANCE_DB", str(tmp_path / "c.db"))
    r = runner.invoke(app, ["grep", r"\bword\b"])
    assert r.exit_code != 0
    assert "regex" in r.stdout.lower() or "support" in r.stdout.lower()
