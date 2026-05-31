"""End-to-end tests for `jw export`."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from jw_cli.main import app

RUNNER = CliRunner()


def _agent_result_json() -> dict:
    return {
        "query": "Es la Trinidad bíblica?",
        "agent_name": "apologetics",
        "warnings": [],
        "metadata": {"language": "es"},
        "findings": [
            {
                "summary": "Jehová es el único Dios verdadero.",
                "excerpt": "",
                "metadata": {},
                "citation": {
                    "url": "https://wol.jw.org/x",
                    "title": "Trinidad",
                    "kind": "article",
                    "metadata": {},
                },
            }
        ],
    }


def _write(tmp_path: Path) -> Path:
    p = tmp_path / "result.json"
    p.write_text(json.dumps(_agent_result_json()), encoding="utf-8")
    return p


def test_export_markdown_smoke(tmp_path: Path) -> None:
    src = _write(tmp_path)
    out = tmp_path / "demo.md"
    result = RUNNER.invoke(app, ["export", str(src), "--format", "markdown", "--out", str(out)])
    assert result.exit_code == 0, result.stdout
    assert out.exists()
    text = out.read_text(encoding="utf-8")
    assert "Trinidad" in text or "trinidad" in text.lower()


def test_export_unknown_format_fails(tmp_path: Path) -> None:
    src = _write(tmp_path)
    result = RUNNER.invoke(app, ["export", str(src), "--format", "bogus", "--out", "/tmp/x"])
    assert result.exit_code != 0


def test_export_missing_input_fails() -> None:
    result = RUNNER.invoke(app, ["export", "/does/not/exist.json", "--format", "markdown", "--out", "/tmp/x.md"])
    assert result.exit_code != 0


def test_export_title_override(tmp_path: Path) -> None:
    src = _write(tmp_path)
    out = tmp_path / "demo.md"
    result = RUNNER.invoke(
        app,
        ["export", str(src), "--format", "markdown", "--out", str(out), "--title", "MiHoja"],
    )
    assert result.exit_code == 0
    assert out.read_text(encoding="utf-8").startswith("# MiHoja")


@pytest.mark.skipif(
    importlib.util.find_spec("weasyprint") is None,
    reason="weasyprint not installed",
)
def test_export_pdf_smoke(tmp_path: Path) -> None:
    src = _write(tmp_path)
    out = tmp_path / "demo.pdf"
    result = RUNNER.invoke(app, ["export", str(src), "--format", "pdf", "--out", str(out)])
    assert result.exit_code == 0, result.stdout
    assert out.read_bytes()[:4] == b"%PDF"
