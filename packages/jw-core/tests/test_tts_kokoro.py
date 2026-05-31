from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from jw_core.audio.tts_providers.fakes import FakeKokoroTTS
from jw_core.audio.tts_providers.kokoro import KokoroTTSProvider


def test_kokoro_real_is_available_when_imports_ok() -> None:
    provider = KokoroTTSProvider()
    # Real availability depends on env; just make sure it never raises
    assert isinstance(provider.is_available(), bool)


def test_kokoro_real_is_unavailable_without_deps() -> None:
    provider = KokoroTTSProvider()
    with patch.object(provider, "_can_import_runtime", return_value=False):
        assert provider.is_available() is False


def test_kokoro_real_synthesize_raises_when_unavailable(tmp_path: Path) -> None:
    provider = KokoroTTSProvider()
    with patch.object(provider, "is_available", return_value=False), pytest.raises(Exception):
        provider.synthesize("hi", voice=None, language="en", output_path=tmp_path / "x.wav")


def test_fake_kokoro_writes_wav(tmp_path: Path) -> None:
    out = FakeKokoroTTS().synthesize("Hola mundo", voice=None, language="es", output_path=tmp_path / "h.wav")
    assert out.exists()
    assert out.suffix == ".wav"
    assert out.stat().st_size > 44  # header + at least 1 frame


def test_fake_kokoro_advertises_target_cpu() -> None:
    assert FakeKokoroTTS.target == "cpu"
    assert "es" in FakeKokoroTTS.languages_supported
