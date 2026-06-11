"""Voice profile registry (Fase 76).

Persists `VoiceProfile` objects as JSON files under
`~/.jw-agent-toolkit/voices/<name>/profile.json`. Honors
`JW_VOICECLONE_ROOT` env override for tests.

Operations: `register`, `list_voices`, `get_voice`, `delete_voice`,
`revoke_consent`.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
from datetime import UTC, datetime
from pathlib import Path

from jw_core.audio.voice_clone.models import VoiceProfile

logger = logging.getLogger(__name__)


class VoiceNotFoundError(KeyError):
    """Raised when a voice name is not registered."""


def default_root() -> Path:
    override = os.environ.get("JW_VOICECLONE_ROOT")
    if override:
        return Path(override).expanduser()
    return Path("~/.jw-agent-toolkit/voices").expanduser()


def _profile_dir(name: str, *, root: Path | None = None) -> Path:
    return (root or default_root()) / name


def _profile_path(name: str, *, root: Path | None = None) -> Path:
    return _profile_dir(name, root=root) / "profile.json"


def register(
    profile: VoiceProfile, *, root: Path | None = None
) -> Path:
    """Persist a `VoiceProfile` and return its on-disk JSON path."""

    p = _profile_path(profile.name, root=root)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(profile.model_dump_json(indent=2))
    return p


def list_voices(*, root: Path | None = None) -> list[VoiceProfile]:
    """Return all registered profiles in stable order by name."""

    base = root or default_root()
    if not base.exists():
        return []
    out: list[VoiceProfile] = []
    for child in sorted(base.iterdir()):
        if not child.is_dir():
            continue
        pjson = child / "profile.json"
        if not pjson.exists():
            continue
        try:
            out.append(
                VoiceProfile.model_validate_json(pjson.read_text())
            )
        except Exception as exc:  # noqa: BLE001
            logger.debug("voice_clone: bad profile at %s: %s", pjson, exc)
            continue
    return out


def get_voice(name: str, *, root: Path | None = None) -> VoiceProfile:
    p = _profile_path(name, root=root)
    if not p.exists():
        raise VoiceNotFoundError(name)
    return VoiceProfile.model_validate_json(p.read_text())


def delete_voice(name: str, *, root: Path | None = None) -> None:
    """Remove the profile dir entirely (consent included)."""

    base = _profile_dir(name, root=root)
    if not base.exists():
        raise VoiceNotFoundError(name)
    shutil.rmtree(base)


def revoke_consent(
    name: str,
    *,
    reason: str | None = None,
    root: Path | None = None,
) -> VoiceProfile:
    """Mark the profile's consent as revoked. Weights remain on disk."""

    profile = get_voice(name, root=root)
    if profile.consent.revoked:
        return profile
    new_consent = profile.consent.model_copy(
        update={
            "revoked": True,
            "revoke_reason": reason,
        }
    )
    updated = profile.model_copy(update={"consent": new_consent})
    register(updated, root=root)
    return updated


def touch_use(
    name: str, *, root: Path | None = None
) -> VoiceProfile:
    """Increment `use_count` and update `last_used_at` after a successful use."""

    profile = get_voice(name, root=root)
    updated = profile.model_copy(
        update={
            "use_count": profile.use_count + 1,
            "last_used_at": datetime.now(UTC),
        }
    )
    register(updated, root=root)
    return updated
