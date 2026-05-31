from __future__ import annotations

from pathlib import Path

import pytest
from jw_gen.cli import gen_app
from typer.testing import CliRunner

runner = CliRunner()


def test_cli_image_with_fake_provider_succeeds(
    tmp_path: Path, isolated_jw_gen_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("JW_GEN_IMAGE_PROVIDER", "fake")
    out = tmp_path / "x.png"
    result = runner.invoke(
        gen_app,
        ["image", "--prompt", "ilustración pacífica de ovejas", "--out", str(out)],
    )
    assert result.exit_code == 0, result.stdout
    assert out.exists()
    assert (tmp_path / "x.png.disclaimer.txt").exists()


def test_cli_image_blocks_logo_prompt(
    tmp_path: Path, isolated_jw_gen_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("JW_GEN_IMAGE_PROVIDER", "fake")
    out = tmp_path / "bad.png"
    result = runner.invoke(
        gen_app,
        ["image", "--prompt", "official watchtower logo", "--out", str(out)],
    )
    assert result.exit_code != 0
    assert not out.exists()
    combined = (result.stdout + (result.stderr or "")).lower()
    assert "logo" in combined or "refused" in combined or "rechazada" in combined


def test_cli_audio_with_fake_provider_succeeds(
    tmp_path: Path, isolated_jw_gen_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("JW_GEN_AUDIO_PROVIDER", "fake")
    out = tmp_path / "bg.wav"
    result = runner.invoke(
        gen_app,
        ["audio", "--prompt", "música suave de fondo", "--out", str(out)],
    )
    assert result.exit_code == 0, result.stdout
    assert out.exists()
    assert (tmp_path / "bg.wav.disclaimer.txt").exists()


def test_cli_no_visible_watermark_logs_audit(
    tmp_path: Path, isolated_jw_gen_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("JW_GEN_IMAGE_PROVIDER", "fake")
    out = tmp_path / "y.png"
    result = runner.invoke(
        gen_app,
        [
            "image",
            "--prompt",
            "campo de trigo",
            "--out",
            str(out),
            "--no-visible-watermark",
        ],
    )
    assert result.exit_code == 0, result.stdout
    assert out.exists()
    audit = (isolated_jw_gen_home / "audit.log").read_text(encoding="utf-8")
    assert "metadata-only" in audit
