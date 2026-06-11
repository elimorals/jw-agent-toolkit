"""Voice profile registry tests (Fase 76)."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from jw_core.audio.voice_clone.models import (
    ConsentRecord,
    TrainingSample,
    VoiceProfile,
)
from jw_core.audio.voice_clone.registry import (
    VoiceNotFoundError,
    delete_voice,
    get_voice,
    list_voices,
    register,
    revoke_consent,
    touch_use,
)


@pytest.fixture(autouse=True)
def _isolated_root(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("JW_VOICECLONE_ROOT", str(tmp_path / "voices"))


def _profile(name: str = "papa") -> VoiceProfile:
    return VoiceProfile(
        name=name,
        provider="fake",
        consent=ConsentRecord(
            signer_name="Juan",
            signer_relationship="parent",
            signed_at=datetime.now(UTC),
            explicit_uses=["read_bible"],
        ),
        samples=[TrainingSample(path="s.wav", duration_s=30.0)],
        weights_path="/tmp/papa.bin",
        created_at=datetime.now(UTC),
    )


def test_register_and_get_roundtrip(tmp_path: Path) -> None:  # noqa: ARG001
    register(_profile())
    out = get_voice("papa")
    assert out.name == "papa"
    assert out.provider == "fake"


def test_get_voice_raises_when_missing() -> None:
    with pytest.raises(VoiceNotFoundError):
        get_voice("does_not_exist")


def test_list_voices_returns_registered() -> None:
    register(_profile("papa"))
    register(_profile("mama"))
    names = {v.name for v in list_voices()}
    assert names == {"papa", "mama"}


def test_revoke_consent_marks_profile() -> None:
    register(_profile())
    updated = revoke_consent("papa", reason="consent withdrawn")
    assert updated.consent.revoked is True
    assert updated.consent.revoke_reason == "consent withdrawn"
    # Persisted
    fresh = get_voice("papa")
    assert fresh.consent.revoked is True


def test_revoke_consent_is_idempotent() -> None:
    register(_profile())
    revoke_consent("papa", reason="r1")
    updated = revoke_consent("papa", reason="r2")
    assert updated.consent.revoke_reason == "r1"


def test_delete_voice_removes_profile() -> None:
    register(_profile())
    delete_voice("papa")
    with pytest.raises(VoiceNotFoundError):
        get_voice("papa")


def test_touch_use_increments_count_and_timestamp() -> None:
    register(_profile())
    before = get_voice("papa").use_count
    updated = touch_use("papa")
    assert updated.use_count == before + 1
    assert updated.last_used_at is not None
