"""CLI smoke tests for `jw book-camera` (Fase 71)."""

from __future__ import annotations

import json

from typer.testing import CliRunner

from jw_cli.commands.book_camera import book_camera_app

runner = CliRunner()


def test_cli_kinds_lists_five() -> None:
    result = runner.invoke(book_camera_app, ["kinds"])
    assert result.exit_code == 0
    for k in (
        "bible_verse",
        "study_question",
        "watchtower_paragraph",
        "plain_text",
        "unknown",
    ):
        assert k in result.stdout


def test_cli_analyze_with_ocr_text_bible_verse() -> None:
    result = runner.invoke(
        book_camera_app,
        ["analyze", "--ocr-text", "Juan 3:16", "-l", "es"],
    )
    assert result.exit_code == 0, result.output
    parsed = json.loads(result.stdout)
    assert parsed["detected"]["kind"] == "bible_verse"


def test_cli_analyze_without_args_fails() -> None:
    result = runner.invoke(book_camera_app, ["analyze"])
    assert result.exit_code != 0
