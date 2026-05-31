from __future__ import annotations

from pathlib import Path

import pytest
from jw_core.audio.tts import TTSError
from jw_core.audio.tts_providers.f5 import F5TTSProvider
from jw_core.audio.tts_providers.fakes import FakeF5TTS


def test_f5_real_is_available_returns_bool() -> None:
    assert isinstance(F5TTSProvider().is_available(), bool)


def test_f5_real_synthesize_raises_when_unavailable(monkeypatch, tmp_path: Path) -> None:
    provider = F5TTSProvider()
    monkeypatch.setattr(provider, "is_available", lambda: False)
    with pytest.raises(TTSError):
        provider.synthesize("hi", voice=None, language="en", output_path=tmp_path / "x.wav")


def test_f5_languages_conservative() -> None:
    # We only declare en officially to avoid over-promising
    assert F5TTSProvider.languages_supported == {"en"}


def test_fake_f5_writes_wav(tmp_path: Path) -> None:
    out = FakeF5TTS().synthesize("hello", voice=None, language="en", output_path=tmp_path / "f.wav")
    assert out.exists()
    assert out.stat().st_size > 0


def test_fake_f5_target_nvidia() -> None:
    assert FakeF5TTS.target == "nvidia"
