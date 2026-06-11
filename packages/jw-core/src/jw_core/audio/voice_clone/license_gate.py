"""License + consent enforcement for family-voice TTS (Fase 76).

Three orthogonal checks:
  - Voice name must not match the deny list (public JW officials).
  - Consent must not be revoked and must not have expired.
  - The text to synthesize must not look like obvious commercial use.

`check_synthesis_allowed()` raises `LicenseGateError` with a descriptive
message; the caller catches and surfaces. There is intentionally no
"override" flag.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime

from jw_core.audio.voice_clone.models import VoiceProfile

# Substrings that disqualify a voice name. Lowercased exact-or-substring
# match. Intentionally conservative; expand carefully.
_NAME_DENY_LIST: tuple[str, ...] = (
    "branch",
    "broadcasting",
    "president",
    "governing_body",
    "governing body",
    "warwick",
)

# Patterns suggesting commercial use of the synthesized voice.
_COMMERCIAL_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\bmarketing\s+campaign\b", re.IGNORECASE),
    re.compile(r"\bsales\s+pitch\b", re.IGNORECASE),
    re.compile(r"\bcommercial\s+(?:use|spot|broadcast)\b", re.IGNORECASE),
    re.compile(r"\bbuy\s+now\b", re.IGNORECASE),
    re.compile(r"\bdiscount\s+offer\b", re.IGNORECASE),
)


class LicenseGateError(RuntimeError):
    """Raised when the license / consent / use-case checks fail."""


def _now() -> datetime:
    return datetime.now(UTC)


def check_voice_name(name: str) -> None:
    """Reject names that match the deny list (case-insensitive)."""

    lowered = name.lower()
    for needle in _NAME_DENY_LIST:
        if needle in lowered:
            raise LicenseGateError(
                f"voice name {name!r} contains denied token "
                f"{needle!r}; pick a personal name instead."
            )


def check_consent_active(profile: VoiceProfile, *, now: datetime | None = None) -> None:
    """Raise if consent is revoked or expired."""

    if profile.consent.revoked:
        raise LicenseGateError(
            f"consent for voice {profile.name!r} has been revoked"
            + (
                f" (reason: {profile.consent.revoke_reason})"
                if profile.consent.revoke_reason
                else ""
            )
        )
    now_dt = now or _now()
    if profile.consent.expires_at is not None:
        if profile.consent.expires_at < now_dt:
            raise LicenseGateError(
                f"consent for voice {profile.name!r} expired at "
                f"{profile.consent.expires_at.isoformat()}"
            )


def check_text_not_commercial(text: str) -> None:
    """Reject text containing obvious commercial-use markers."""

    if not text:
        return
    for pat in _COMMERCIAL_PATTERNS:
        if pat.search(text):
            raise LicenseGateError(
                f"text matches commercial-use pattern "
                f"{pat.pattern!r}; refusing synthesis."
            )


def check_synthesis_allowed(
    profile: VoiceProfile,
    text: str,
    *,
    now: datetime | None = None,
) -> None:
    """All-in-one gate; raises `LicenseGateError` on any failure."""

    check_voice_name(profile.name)
    check_consent_active(profile, now=now)
    check_text_not_commercial(text)
