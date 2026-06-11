"""CLI smoke tests for `jw voiceclone` (Fase 76)."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from typer.testing import CliRunner

from jw_cli.commands.voiceclone import voiceclone_app

runner = CliRunner()


@pytest.fixture(autouse=True)
def _isolated_root(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("JW_VOICECLONE_ROOT", str(tmp_path / "voices"))


def _consent_file(p: Path) -> Path:
    p.write_text(
        json.dumps(
            {
                "signer_name": "Juan",
                "signer_relationship": "parent",
                "signed_at": datetime.now(UTC).isoformat(),
                "explicit_uses": ["read_bible"],
            }
        )
    )
    return p


def test_cli_register_then_list(tmp_path: Path) -> None:
    consent = _consent_file(tmp_path / "consent.json")
    result = runner.invoke(
        voiceclone_app,
        [
            "register-from-consent",
            "papa",
            "--consent-file",
            str(consent),
        ],
    )
    assert result.exit_code == 0, result.output

    listed = runner.invoke(voiceclone_app, ["list"])
    assert listed.exit_code == 0
    assert "papa" in listed.stdout


def test_cli_show_unknown_voice_exits_nonzero() -> None:
    result = runner.invoke(voiceclone_app, ["show", "ghost"])
    assert result.exit_code != 0


def test_cli_revoke_then_show_shows_revoked(tmp_path: Path) -> None:
    consent = _consent_file(tmp_path / "consent.json")
    runner.invoke(
        voiceclone_app,
        [
            "register-from-consent",
            "papa",
            "--consent-file",
            str(consent),
        ],
    )
    revoked = runner.invoke(
        voiceclone_app, ["revoke", "papa", "--reason", "testing"]
    )
    assert revoked.exit_code == 0
    shown = runner.invoke(voiceclone_app, ["show", "papa"])
    assert shown.exit_code == 0
    assert '"revoked":' in shown.stdout
    assert '"revoke_reason": "testing"' in shown.stdout


def test_cli_say_blocked_after_revoke(tmp_path: Path) -> None:
    consent = _consent_file(tmp_path / "consent.json")
    runner.invoke(
        voiceclone_app,
        [
            "register-from-consent",
            "papa",
            "--consent-file",
            str(consent),
        ],
    )
    runner.invoke(voiceclone_app, ["revoke", "papa"])
    out = runner.invoke(
        voiceclone_app,
        [
            "say",
            "papa",
            "Salmo 23",
            "--output",
            str(tmp_path / "out.wav"),
        ],
    )
    assert out.exit_code == 2  # license gate code
    assert "license gate" in out.stdout.lower()


def test_cli_delete_requires_confirm(tmp_path: Path) -> None:
    consent = _consent_file(tmp_path / "consent.json")
    runner.invoke(
        voiceclone_app,
        [
            "register-from-consent",
            "papa",
            "--consent-file",
            str(consent),
        ],
    )
    nope = runner.invoke(voiceclone_app, ["delete", "papa"])
    assert nope.exit_code != 0
    yep = runner.invoke(
        voiceclone_app, ["delete", "papa", "--confirm"]
    )
    assert yep.exit_code == 0


def test_cli_say_writes_wav_when_allowed(tmp_path: Path) -> None:
    consent = _consent_file(tmp_path / "consent.json")
    runner.invoke(
        voiceclone_app,
        [
            "register-from-consent",
            "papa",
            "--consent-file",
            str(consent),
        ],
    )
    out_path = tmp_path / "out.wav"
    result = runner.invoke(
        voiceclone_app,
        [
            "say",
            "papa",
            "Lectura del Salmo 23",
            "--output",
            str(out_path),
        ],
    )
    assert result.exit_code == 0, result.output
    assert out_path.exists()
