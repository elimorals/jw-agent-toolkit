from __future__ import annotations

from pathlib import Path

import pytest
from jw_core.audio.asr_providers.deepgram import DeepgramProvider
from jw_core.audio.asr_providers.fakes import FakeDeepgram
from jw_core.audio.transcription import TranscriptionError


def test_deepgram_unavailable_without_key(monkeypatch) -> None:
    monkeypatch.delenv("DEEPGRAM_API_KEY", raising=False)
    assert DeepgramProvider().is_available() is False


def test_deepgram_available_with_key(monkeypatch) -> None:
    monkeypatch.setenv("DEEPGRAM_API_KEY", "dg-test")
    assert DeepgramProvider().is_available() is True


def test_deepgram_transcribe_raises_without_key(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.delenv("DEEPGRAM_API_KEY", raising=False)
    audio = tmp_path / "a.wav"
    audio.write_bytes(b"\x00")
    with pytest.raises(TranscriptionError):
        DeepgramProvider().transcribe(audio, language="en", model_size="auto")


def test_deepgram_transcribe_via_http(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("DEEPGRAM_API_KEY", "dg-test")
    audio = tmp_path / "a.wav"
    audio.write_bytes(b"AUDIO_BYTES")

    captured: dict[str, object] = {}

    class FakeResp:
        status_code = 200

        def raise_for_status(self) -> None: ...

        def json(self) -> dict:
            return {
                "results": {
                    "channels": [
                        {
                            "alternatives": [
                                {
                                    "transcript": "hello from deepgram",
                                    "confidence": 0.95,
                                }
                            ],
                            "detected_language": "en",
                        }
                    ]
                },
                "metadata": {"duration": 1.5},
            }

    class FakeClient:
        def __init__(self, *a, **kw) -> None: ...
        def __enter__(self):
            return self

        def __exit__(self, *a) -> None: ...
        def post(self, url, **kw):
            captured["url"] = url
            captured["headers"] = kw.get("headers")
            captured["data"] = kw.get("content")
            return FakeResp()

    monkeypatch.setattr("httpx.Client", FakeClient)
    monkeypatch.setattr(DeepgramProvider, "_use_sdk", lambda self: False)

    result = DeepgramProvider().transcribe(audio, language="en", model_size="auto")
    assert result.text == "hello from deepgram"
    assert result.language == "en"
    assert captured["headers"]["Authorization"] == "Token dg-test"


def test_fake_deepgram(tmp_path: Path) -> None:
    audio = tmp_path / "a.wav"
    audio.write_bytes(b"\x00")
    r = FakeDeepgram().transcribe(audio, language="es", model_size="auto")
    assert r.text
    assert FakeDeepgram.target == "api"
