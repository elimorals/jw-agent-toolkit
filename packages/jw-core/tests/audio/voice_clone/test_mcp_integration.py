"""F76 MCP tool integration."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from pathlib import Path

import pytest

from jw_core.audio.voice_clone.models import (
    ConsentRecord,
    VoiceProfile,
)
from jw_core.audio.voice_clone.registry import register


def _call(tool, **kwargs):
    fn = getattr(tool, "fn", tool)
    return asyncio.run(fn(**kwargs))


@pytest.fixture(autouse=True)
def _isolated_root(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("JW_VOICECLONE_ROOT", str(tmp_path / "voices"))


def _register_papa() -> None:
    register(
        VoiceProfile(
            name="papa",
            provider="fake",
            consent=ConsentRecord(
                signer_name="Juan",
                signer_relationship="parent",
                signed_at=datetime.now(UTC),
                explicit_uses=["read_bible"],
            ),
            weights_path="/tmp/x",
            created_at=datetime.now(UTC),
        )
    )


def test_mcp_list_voices_empty() -> None:
    from jw_mcp.server import voice_clone_list

    out = _call(voice_clone_list)
    assert isinstance(out, dict)
    assert out["voices"] == []


def test_mcp_synthesize_then_audit(tmp_path: Path) -> None:
    from jw_mcp.server import voice_clone_audit, voice_clone_synthesize

    _register_papa()
    out_path = tmp_path / "out.wav"
    out = _call(
        voice_clone_synthesize,
        voice_name="papa",
        text="Lectura del Salmo 23",
        output_path=str(out_path),
    )
    assert out["ok"] is True
    assert Path(out["path"]).exists()

    audit = _call(voice_clone_audit, voice_name="papa")
    assert audit["ok"] is True
    assert audit["use_count"] == 1
    assert audit["last_used_at"] is not None
    assert audit["consent_revoked"] is False


def test_mcp_synthesize_returns_error_dict_on_missing(tmp_path: Path) -> None:
    from jw_mcp.server import voice_clone_synthesize

    out = _call(
        voice_clone_synthesize,
        voice_name="ghost",
        text="x",
        output_path=str(tmp_path / "out.wav"),
    )
    assert out["ok"] is False
    assert "voice not found" in out["error"]


def test_mcp_synthesize_returns_error_dict_on_commercial(
    tmp_path: Path,
) -> None:
    from jw_mcp.server import voice_clone_synthesize

    _register_papa()
    out = _call(
        voice_clone_synthesize,
        voice_name="papa",
        text="speech for marketing campaign",
        output_path=str(tmp_path / "out.wav"),
    )
    assert out["ok"] is False
    assert "commercial" in out["error"].lower()
