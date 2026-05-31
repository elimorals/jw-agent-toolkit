from __future__ import annotations

from unittest.mock import patch

import pytest
from jw_core.audio.tts import (
    DEFAULT_TTS_CHAIN,
    TTSError,
    get_tts_provider,
    list_tts_providers,
)


def test_default_chain_starts_with_kokoro() -> None:
    assert DEFAULT_TTS_CHAIN[0] == "kokoro_local"
    assert "edge" in DEFAULT_TTS_CHAIN
    assert "system" in DEFAULT_TTS_CHAIN
    assert "elevenlabs" in DEFAULT_TTS_CHAIN
    assert "piper" in DEFAULT_TTS_CHAIN


def test_list_includes_premium_providers() -> None:
    names = {p["name"] for p in list_tts_providers()}
    assert {"kokoro_local", "elevenlabs", "xtts", "f5", "edge", "system", "piper"}.issubset(names)


def test_get_tts_provider_falls_back_through_chain(monkeypatch) -> None:
    """When kokoro isn't available we should get edge/system, not an error."""
    monkeypatch.delenv("JW_TTS_PROVIDER", raising=False)
    # Kokoro unavailable
    with patch(
        "jw_core.audio.tts_providers.kokoro.KokoroTTSProvider.is_available",
        return_value=False,
    ):
        provider = get_tts_provider()
        assert provider.name in {"edge", "system", "elevenlabs", "piper"}


def test_jw_tts_provider_env_forces_choice(monkeypatch) -> None:
    monkeypatch.setenv("JW_TTS_PROVIDER", "system")
    p = get_tts_provider()
    assert p.name == "system"


def test_jw_tts_provider_unavailable_raises(monkeypatch) -> None:
    monkeypatch.setenv("JW_TTS_PROVIDER", "kokoro_local")
    with (
        patch(
            "jw_core.audio.tts_providers.kokoro.KokoroTTSProvider.is_available",
            return_value=False,
        ),
        pytest.raises(TTSError, match="kokoro_local"),
    ):
        get_tts_provider()


def test_existing_providers_still_present_unchanged() -> None:
    """The 3 original providers must not be renamed or removed."""
    names = {p["name"] for p in list_tts_providers()}
    assert {"system", "edge", "piper"}.issubset(names)
