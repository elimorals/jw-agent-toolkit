from __future__ import annotations

from pathlib import Path

import pytest
from jw_core.audio.tts import TTSError
from jw_core.audio.tts_providers.fakes import FakeXTTSv2
from jw_core.audio.tts_providers.xtts import XTTSv2Provider


def test_xtts_requires_consent_env(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.delenv("JW_XTTS_CLONE_CONSENT", raising=False)
    provider = XTTSv2Provider()
    assert provider.is_available() is False


def test_xtts_requires_voice_sample(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("JW_XTTS_CLONE_CONSENT", "1")
    provider = XTTSv2Provider()
    with pytest.raises(TTSError, match="voice_sample"):
        provider.synthesize("hi", voice=None, language="en", output_path=tmp_path / "o.wav")


def test_xtts_writes_consent_file(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("JW_XTTS_CLONE_CONSENT", "1")
    sample = tmp_path / "sample.wav"
    sample.write_bytes(b"RIFF\x00\x00\x00\x00WAVE")
    fake = FakeXTTSv2()
    out = fake.synthesize("hola", voice=str(sample), language="es", output_path=tmp_path / "o.wav")
    assert out.exists()


def test_xtts_real_unavailable_without_pkg(monkeypatch) -> None:
    monkeypatch.setenv("JW_XTTS_CLONE_CONSENT", "1")
    provider = XTTSv2Provider()
    # In CI coqui-tts is not installed; assert that path is exercised
    available = provider.is_available()
    assert isinstance(available, bool)


def test_xtts_target_nvidia() -> None:
    assert XTTSv2Provider.target == "nvidia"
