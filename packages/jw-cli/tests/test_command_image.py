from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from jw_cli.commands.image import image_app


def _img(tmp_path: Path) -> Path:
    p = tmp_path / "x.png"
    p.write_bytes(b"\x89PNG")
    return p


def test_extract_uses_fake_provider(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("JW_VLM_PROVIDER", "fake")
    runner = CliRunner()
    result = runner.invoke(image_app, ["extract", str(_img(tmp_path)), "--language", "en"])
    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout)
    assert "blocks" in payload
    assert payload["provider_name"] == "fake"


def test_ingest_command_runs(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("JW_VLM_PROVIDER", "fake")
    runner = CliRunner()
    out = runner.invoke(
        image_app,
        ["ingest", str(_img(tmp_path)), "--language", "en", "--store", str(tmp_path / "store")],
    )
    assert out.exit_code == 0, out.stdout
    assert "chunks" in out.stdout.lower()
