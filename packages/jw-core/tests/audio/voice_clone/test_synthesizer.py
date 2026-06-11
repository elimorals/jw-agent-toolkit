"""Synthesizer end-to-end tests (Fase 76)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from jw_core.audio.voice_clone.license_gate import LicenseGateError
from jw_core.audio.voice_clone.models import (
    ConsentRecord,
    VoiceProfile,
)
from jw_core.audio.voice_clone.registry import (
    VoiceNotFoundError,
    register,
)
from jw_core.audio.voice_clone.synthesizer import (
    FakeVoiceProvider,
    synthesize_with_voice,
)


@pytest.fixture(autouse=True)
def _isolated_root(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("JW_VOICECLONE_ROOT", str(tmp_path / "voices"))


def _register_papa(
    *,
    revoked: bool = False,
    expires_at: datetime | None = None,
    name: str = "papa",
) -> VoiceProfile:
    profile = VoiceProfile(
        name=name,
        provider="fake",
        consent=ConsentRecord(
            signer_name="Juan",
            signer_relationship="parent",
            signed_at=datetime.now(UTC),
            expires_at=expires_at,
            revoked=revoked,
        ),
        weights_path="/tmp/papa.bin",
        created_at=datetime.now(UTC),
    )
    register(profile)
    return profile


def test_synthesize_with_voice_happy_path(tmp_path: Path) -> None:
    _register_papa()
    out_path = tmp_path / "out.wav"
    written = synthesize_with_voice(
        "papa", "Lectura familiar", str(out_path)
    )
    assert written.exists()
    content = written.read_bytes()
    assert content.startswith(b"FAKEWAV::")


def test_synthesize_unknown_voice_raises(tmp_path: Path) -> None:
    out_path = tmp_path / "x.wav"
    with pytest.raises(VoiceNotFoundError):
        synthesize_with_voice("ghost", "anything", str(out_path))


def test_synthesize_revoked_consent_raises(tmp_path: Path) -> None:
    _register_papa(revoked=True)
    out_path = tmp_path / "x.wav"
    with pytest.raises(LicenseGateError, match="revoked"):
        synthesize_with_voice("papa", "ok", str(out_path))


def test_synthesize_expired_consent_raises(tmp_path: Path) -> None:
    _register_papa(
        expires_at=datetime.now(UTC) - timedelta(days=1)
    )
    out_path = tmp_path / "x.wav"
    with pytest.raises(LicenseGateError, match="expired"):
        synthesize_with_voice("papa", "ok", str(out_path))


def test_synthesize_commercial_text_raises(tmp_path: Path) -> None:
    _register_papa()
    out_path = tmp_path / "x.wav"
    with pytest.raises(LicenseGateError, match="commercial"):
        synthesize_with_voice(
            "papa", "speech for marketing campaign", str(out_path)
        )


def test_synthesize_denied_name_raises(tmp_path: Path) -> None:
    _register_papa(name="branch reader")
    out_path = tmp_path / "x.wav"
    with pytest.raises(LicenseGateError, match="denied token"):
        synthesize_with_voice("branch reader", "ok", str(out_path))


def test_synthesize_increments_use_count(tmp_path: Path) -> None:
    from jw_core.audio.voice_clone.registry import get_voice

    _register_papa()
    out_path = tmp_path / "out.wav"
    synthesize_with_voice("papa", "Salmo 23", str(out_path))
    synthesize_with_voice(
        "papa", "Mateo 6:9", str(tmp_path / "out2.wav")
    )
    profile = get_voice("papa")
    assert profile.use_count == 2
    assert profile.last_used_at is not None


def test_synthesize_emit_trace_callback(tmp_path: Path) -> None:
    _register_papa()
    events: list[dict] = []

    def emit(*, name: str, payload: dict) -> None:
        events.append({"name": name, **payload})

    out_path = tmp_path / "x.wav"
    synthesize_with_voice(
        "papa", "Salmo 23", str(out_path), emit_trace=emit
    )
    assert events
    assert events[0]["name"] == "voice_used"
    assert events[0]["provider"] == "fake"


def test_fake_provider_is_deterministic(tmp_path: Path) -> None:
    provider = FakeVoiceProvider()
    a = provider.synthesize(
        text="hi", weights_path="/tmp/x", output_path=tmp_path / "a.wav"
    )
    b = provider.synthesize(
        text="hi", weights_path="/tmp/x", output_path=tmp_path / "b.wav"
    )
    assert a.read_bytes() == b.read_bytes()
