from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from jw_core.audio.tts import TTSError
from jw_core.audio.tts_providers.elevenlabs import ElevenLabsProvider
from jw_core.audio.tts_providers.fakes import FakeElevenLabsTTS


def test_elevenlabs_unavailable_without_key(monkeypatch) -> None:
    monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)
    assert ElevenLabsProvider().is_available() is False


def test_elevenlabs_available_with_key(monkeypatch) -> None:
    monkeypatch.setenv("ELEVENLABS_API_KEY", "sk-test")
    # is_available must not hit the network
    assert ElevenLabsProvider().is_available() is True


def test_elevenlabs_synthesize_raises_without_key(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)
    with pytest.raises(TTSError):
        ElevenLabsProvider().synthesize(
            "hi", voice=None, language="en", output_path=tmp_path / "x.mp3"
        )


def test_elevenlabs_uses_httpx_with_voice_id(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("ELEVENLABS_API_KEY", "sk-test")
    monkeypatch.setenv("ELEVENLABS_VOICE_ID", "my-voice")

    called = {}

    class FakeResp:
        status_code = 200
        content = b"ID3FAKEMP3"

        def raise_for_status(self) -> None: ...

    class FakeClient:
        def __init__(self, *a, **kw) -> None:
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a) -> None: ...

        def post(self, url, **kw):
            called["url"] = url
            called["json"] = kw.get("json")
            called["headers"] = kw.get("headers")
            return FakeResp()

    monkeypatch.setattr("httpx.Client", FakeClient)
    monkeypatch.setattr(
        ElevenLabsProvider, "_use_sdk", lambda self: False, raising=True
    )

    out = ElevenLabsProvider().synthesize(
        "hello", voice=None, language="en", output_path=tmp_path / "h.mp3"
    )
    assert out.exists()
    assert out.read_bytes() == b"ID3FAKEMP3"
    assert "my-voice" in called["url"]
    assert called["headers"]["xi-api-key"] == "sk-test"


def test_fake_elevenlabs_target_api() -> None:
    assert FakeElevenLabsTTS.target == "api"
