"""Synthesizer entry point with license enforcement (Fase 76).

`synthesize_with_voice(name, text, output_path, ...)` runs the gate,
delegates to a `VoiceProvider` (Fake by default), persists usage,
and optionally emits a trace audit event (F43).
"""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path
from typing import Any, Protocol

from jw_core.audio.voice_clone.license_gate import (
    LicenseGateError,
    check_synthesis_allowed,
)
from jw_core.audio.voice_clone.models import VoiceProfile
from jw_core.audio.voice_clone.registry import (
    VoiceNotFoundError,
    get_voice,
    touch_use,
)

logger = logging.getLogger(__name__)


class VoiceProvider(Protocol):
    """Provider that turns (text, weights_path) into a WAV file path."""

    name: str

    def synthesize(
        self, *, text: str, weights_path: str, output_path: Path
    ) -> Path: ...


class FakeVoiceProvider:
    """Deterministic provider used in tests and as the default fallback.

    Writes a small "fake WAV" payload whose content is a SHA-256 of the
    text + weights hint; this lets callers verify identity without
    needing a real model.
    """

    name = "fake"

    def synthesize(
        self, *, text: str, weights_path: str, output_path: Path
    ) -> Path:
        digest = hashlib.sha256(
            text.encode("utf-8") + b"::" + weights_path.encode("utf-8")
        ).hexdigest()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(
            b"FAKEWAV::" + digest.encode("ascii") + b"\n"
        )
        return output_path


def synthesize_with_voice(
    voice_name: str,
    text: str,
    output_path: str | Path,
    *,
    provider: VoiceProvider | None = None,
    root: Path | None = None,
    emit_trace: Any | None = None,
) -> Path:
    """High-level entry point.

    Steps:
        1. Resolve the `VoiceProfile`.
        2. Run the license gate.
        3. Delegate to the provider.
        4. Touch usage in the registry.
        5. Optionally emit a trace audit event.

    Raises `VoiceNotFoundError` / `LicenseGateError` on policy failure.
    """

    profile: VoiceProfile = get_voice(voice_name, root=root)
    check_synthesis_allowed(profile, text)

    backend = provider or FakeVoiceProvider()
    out = backend.synthesize(
        text=text,
        weights_path=profile.weights_path,
        output_path=Path(output_path),
    )
    touch_use(voice_name, root=root)

    if emit_trace is not None:
        try:
            emit_trace(
                name="voice_used",
                payload={
                    "voice_name": voice_name,
                    "text_sha256": hashlib.sha256(
                        text.encode("utf-8")
                    ).hexdigest()[:16],
                    "provider": backend.name,
                    "output_path": str(out),
                },
            )
        except Exception as exc:  # noqa: BLE001
            logger.debug("voice trace emit failed: %s", exc)
    return out


__all__ = [
    "FakeVoiceProvider",
    "LicenseGateError",
    "VoiceNotFoundError",
    "VoiceProvider",
    "synthesize_with_voice",
]
