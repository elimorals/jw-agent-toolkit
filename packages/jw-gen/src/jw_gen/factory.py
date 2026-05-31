"""Provider routing.

Strategy:
  1. Explicit `provider=` kwarg wins.
  2. Else env JW_GEN_<KIND>_PROVIDER.
  3. Else default fallback chain per kind, picking first `is_available()`.
  4. If nothing available, fall back to fake (when `allow_fake_fallback=True`).

The fake is ALWAYS reachable when explicitly named or env-set so tests stay
hermetic. Pass `allow_fake_fallback=False` to assert NoProviderAvailable
when nothing real is available (the CI behavior).
"""

from __future__ import annotations

import os
from typing import cast

from jw_gen.models import Kind
from jw_gen.providers.base import GenerationProvider
from jw_gen.providers.fakes import (
    FakeAudioProvider,
    FakeImageProvider,
    FakeVideoProvider,
)


class NoProviderAvailable(RuntimeError):
    """Raised when no usable provider can be resolved for a kind."""


_FALLBACK: dict[Kind, list[str]] = {
    "image": ["nanobanana", "flux2", "recraft", "ideogram", "imagen"],
    "audio": ["elevenlabs", "musicgen", "suno"],
    "video": ["veo3", "kling", "seedance", "runway", "higgsfield"],
}


def _build(name: str, kind: Kind) -> GenerationProvider | None:
    n = name.lower()
    if n == "fake":
        if kind == "image":
            return cast(GenerationProvider, FakeImageProvider())
        if kind == "audio":
            return cast(GenerationProvider, FakeAudioProvider())
        if kind == "video":
            return cast(GenerationProvider, FakeVideoProvider())

    if kind == "image" and n == "nanobanana":
        try:
            from jw_gen.providers.image.nanobanana import NanoBananaProvider

            return cast(GenerationProvider, NanoBananaProvider())
        except Exception:  # noqa: BLE001
            return None
    if kind == "audio" and n == "elevenlabs":
        try:
            from jw_gen.providers.audio.elevenlabs import ElevenLabsProvider

            return cast(GenerationProvider, ElevenLabsProvider())
        except Exception:  # noqa: BLE001
            return None
    if kind == "video" and n == "veo3":
        try:
            from jw_gen.providers.video.veo3 import Veo3Provider

            return cast(GenerationProvider, Veo3Provider())
        except Exception:  # noqa: BLE001
            return None

    return None


def get_provider(
    kind: Kind,
    *,
    provider: str | None = None,
    allow_fake_fallback: bool = True,
) -> GenerationProvider:
    """Resolve a provider for `kind`. Raise NoProviderAvailable if nothing fits.

    `allow_fake_fallback=True` (default) appends `fake` as the last candidate so
    test environments never accidentally hit the network. CI / production may
    pass `False` to force a real explicit provider choice.
    """

    candidates: list[str] = []
    if provider:
        candidates.append(provider)
    env_key = f"JW_GEN_{kind.upper()}_PROVIDER"
    env_choice = os.environ.get(env_key)
    if env_choice and env_choice not in candidates:
        candidates.append(env_choice)
    for default in _FALLBACK.get(kind, []):
        if default not in candidates:
            candidates.append(default)
    if allow_fake_fallback:
        candidates.append("fake")

    last_attempt: str | None = None
    for name in candidates:
        last_attempt = name
        built = _build(name, kind)
        if built is not None and built.is_available():
            return built

    raise NoProviderAvailable(
        f"No provider available for kind={kind!r}. Tried: {candidates}. "
        f"Last attempt: {last_attempt}. "
        f"Set {env_key} or pass provider= explicitly."
    )
