"""Pydantic models for consented family-voice TTS (Fase 76)."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

License = Literal[
    "personal_family_only",
    "personal_education_only",
]
Provider = Literal["f5tts", "xttsv2", "fake"]
SignerRelationship = Literal[
    "self", "parent", "spouse", "child", "sibling", "other"
]


class ConsentRecord(BaseModel):
    signer_name: str
    signer_relationship: SignerRelationship
    signed_at: datetime
    explicit_uses: list[str] = Field(default_factory=list)
    expires_at: datetime | None = None
    revoked: bool = False
    revoke_reason: str | None = None


class TrainingSample(BaseModel):
    path: str
    duration_s: float = Field(ge=0)
    snr_db: float = 0.0
    sample_rate_hz: int = Field(default=16000, ge=8000)
    transcript: str = ""


class VoiceProfile(BaseModel):
    name: str
    provider: Provider
    consent: ConsentRecord
    license: License = "personal_family_only"
    samples: list[TrainingSample] = Field(default_factory=list)
    weights_path: str
    weights_encrypted: bool = False
    created_at: datetime
    last_used_at: datetime | None = None
    use_count: int = Field(default=0, ge=0)
    trace_audit_path: str | None = None


class TrainResult(BaseModel):
    profile: VoiceProfile
    validation_sample_path: str
    training_log_path: str
    duration_s: float = Field(ge=0)
