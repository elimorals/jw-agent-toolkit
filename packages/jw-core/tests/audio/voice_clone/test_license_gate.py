"""License gate tests (Fase 76)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from jw_core.audio.voice_clone.license_gate import (
    LicenseGateError,
    check_consent_active,
    check_synthesis_allowed,
    check_text_not_commercial,
    check_voice_name,
)
from jw_core.audio.voice_clone.models import (
    ConsentRecord,
    VoiceProfile,
)


def _consent(
    *, revoked: bool = False, expires_in: int | None = None
) -> ConsentRecord:
    return ConsentRecord(
        signer_name="Juan",
        signer_relationship="parent",
        signed_at=datetime.now(UTC),
        expires_at=(
            datetime.now(UTC) + timedelta(days=expires_in)
            if expires_in is not None
            else None
        ),
        revoked=revoked,
    )


def _profile(name: str = "papa", **kw) -> VoiceProfile:
    return VoiceProfile(
        name=name,
        provider="fake",
        consent=kw.get("consent", _consent()),
        weights_path="/tmp/x.bin",
        created_at=datetime.now(UTC),
    )


def test_check_voice_name_rejects_president() -> None:
    with pytest.raises(LicenseGateError, match="denied token"):
        check_voice_name("President of Branch")


def test_check_voice_name_accepts_personal_name() -> None:
    check_voice_name("papa")  # no raise


def test_check_consent_active_rejects_revoked() -> None:
    p = _profile(consent=_consent(revoked=True))
    with pytest.raises(LicenseGateError, match="revoked"):
        check_consent_active(p)


def test_check_consent_active_rejects_expired() -> None:
    p = _profile(consent=_consent(expires_in=-1))
    with pytest.raises(LicenseGateError, match="expired"):
        check_consent_active(p)


def test_check_consent_active_accepts_future_expiry() -> None:
    p = _profile(consent=_consent(expires_in=30))
    check_consent_active(p)


def test_check_consent_active_accepts_no_expiry() -> None:
    p = _profile()
    check_consent_active(p)


def test_check_text_not_commercial_rejects_marketing() -> None:
    with pytest.raises(LicenseGateError, match="commercial-use pattern"):
        check_text_not_commercial("speech for marketing campaign")


def test_check_text_not_commercial_accepts_neutral() -> None:
    check_text_not_commercial(
        "Lectura familiar de Juan 3 versículo 16."
    )


def test_check_synthesis_allowed_full_pipeline_ok() -> None:
    p = _profile(consent=_consent(expires_in=30))
    check_synthesis_allowed(p, "Lectura del Salmo 23.")


def test_check_synthesis_allowed_rejects_chain_on_first_failure() -> None:
    p = _profile(name="Branch Office Reader")
    with pytest.raises(LicenseGateError):
        check_synthesis_allowed(p, "ok text")
