"""Voice-clone Pydantic models."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from jw_core.audio.voice_clone.models import (
    ConsentRecord,
    TrainingSample,
    VoiceProfile,
)


def _consent(**overrides) -> ConsentRecord:
    base = {
        "signer_name": "Juan Pérez",
        "signer_relationship": "parent",
        "signed_at": datetime.now(UTC),
        "explicit_uses": ["read_bible"],
    }
    base.update(overrides)
    return ConsentRecord(**base)


def test_consent_record_defaults() -> None:
    c = _consent()
    assert c.revoked is False
    assert c.explicit_uses == ["read_bible"]


def test_consent_record_rejects_unknown_relationship() -> None:
    with pytest.raises(ValueError):
        ConsentRecord(
            signer_name="x",
            signer_relationship="cousin",  # type: ignore[arg-type]
            signed_at=datetime.now(UTC),
        )


def test_training_sample_rejects_low_sample_rate() -> None:
    with pytest.raises(ValueError):
        TrainingSample(
            path="x.wav", duration_s=10.0, sample_rate_hz=4000
        )


def test_voice_profile_round_trip() -> None:
    p = VoiceProfile(
        name="papa",
        provider="fake",
        consent=_consent(),
        samples=[TrainingSample(path="s.wav", duration_s=30.0)],
        weights_path="/tmp/papa.bin",
        created_at=datetime.now(UTC),
    )
    dumped = p.model_dump()
    rehydrated = VoiceProfile.model_validate(dumped)
    assert rehydrated.name == "papa"
    assert rehydrated.license == "personal_family_only"
    assert rehydrated.use_count == 0


def test_voice_profile_rejects_invalid_provider() -> None:
    with pytest.raises(ValueError):
        VoiceProfile(
            name="x",
            provider="elevenlabs",  # type: ignore[arg-type]
            consent=_consent(),
            weights_path="x",
            created_at=datetime.now(UTC),
        )
