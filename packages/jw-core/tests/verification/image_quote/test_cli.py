"""CLI smoke tests for `jw verify-image` (Fase 70)."""

from __future__ import annotations

import json
from pathlib import Path

from PIL import Image
from typer.testing import CliRunner

from jw_cli.commands.verify_image import verify_image_app

runner = CliRunner()


def _img(p: Path) -> None:
    Image.new("RGB", (32, 32), color=(120, 200, 80)).save(p, "JPEG")


def test_cli_verdicts_lists_four_actions() -> None:
    result = runner.invoke(verify_image_app, ["verdicts"])
    assert result.exit_code == 0
    for v in ("SUPPORTED", "DISTORTED", "FABRICATED", "UNVERIFIABLE"):
        assert v in result.stdout


def test_cli_check_with_ocr_override(tmp_path: Path) -> None:
    img = tmp_path / "x.jpg"
    _img(img)
    result = runner.invoke(
        verify_image_app,
        [
            "check",
            str(img),
            "-l",
            "es",
            "--ocr-text",
            "Que el amor de Jehová guíe nuestras decisiones según el reino.",
        ],
    )
    assert result.exit_code == 0, result.output
    parsed = json.loads(result.stdout)
    assert parsed["verdict"] in (
        "SUPPORTED",
        "DISTORTED",
        "FABRICATED",
        "UNVERIFIABLE",
    )


def test_cli_check_brief_mode(tmp_path: Path) -> None:
    img = tmp_path / "x.jpg"
    _img(img)
    result = runner.invoke(
        verify_image_app,
        [
            "check",
            str(img),
            "--ocr-text",
            "hi",
            "--brief",
        ],
    )
    assert result.exit_code == 0
    assert "verdict" in result.stdout
    assert "UNVERIFIABLE" in result.stdout
