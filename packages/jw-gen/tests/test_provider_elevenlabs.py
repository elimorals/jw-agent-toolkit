"""Offline unit tests for ElevenLabs adapter."""

from __future__ import annotations

import sys
import types
from pathlib import Path

import pytest
from jw_gen.models import GenerationRequest


def test_is_available_false_when_no_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)
    from jw_gen.providers.audio.elevenlabs import ElevenLabsProvider

    assert ElevenLabsProvider().is_available() is False


def test_is_available_false_when_sdk_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ELEVENLABS_API_KEY", "fake-key")
    monkeypatch.setitem(sys.modules, "elevenlabs", None)
    from jw_gen.providers.audio.elevenlabs import ElevenLabsProvider

    assert ElevenLabsProvider().is_available() is False


def test_cost_estimate_scales_with_prompt_length(tmp_path: Path) -> None:
    from jw_gen.providers.audio.elevenlabs import ElevenLabsProvider

    p = ElevenLabsProvider(work_dir=tmp_path)
    short = p.cost_estimate(GenerationRequest(prompt="x", kind="audio"))
    long_ = p.cost_estimate(GenerationRequest(prompt="x" * 1000, kind="audio"))
    assert long_.usd > short.usd


def test_generate_writes_mp3_and_passes_correct_args(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    captured: dict = {}

    class _FakeTTS:
        def convert(self, *, voice_id: str, output_format: str, text: str):
            captured["voice_id"] = voice_id
            captured["output_format"] = output_format
            captured["text"] = text
            return iter([b"ID3", b"\x03\x00\x00\x00", b"FAKE_MP3_DATA"])

    class _FakeClient:
        def __init__(self, api_key: str) -> None:
            captured["api_key"] = api_key
            self.text_to_speech = _FakeTTS()

    fake_module = types.SimpleNamespace(ElevenLabs=_FakeClient)
    monkeypatch.setitem(sys.modules, "elevenlabs", fake_module)
    monkeypatch.setenv("ELEVENLABS_API_KEY", "fake-key")

    from jw_gen.providers.audio.elevenlabs import ElevenLabsProvider

    p = ElevenLabsProvider(work_dir=tmp_path)
    out = p.generate(GenerationRequest(prompt="Hola mundo", kind="audio", extra={"voice_id": "v1"}))
    assert out.suffix == ".mp3"
    assert out.read_bytes().startswith(b"ID3")
    assert captured["voice_id"] == "v1"
    assert captured["text"] == "Hola mundo"
    assert captured["api_key"] == "fake-key"


def test_generate_uses_default_voice_when_none_specified(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    captured: dict = {}

    class _FakeTTS:
        def convert(self, *, voice_id: str, output_format: str, text: str):
            captured["voice_id"] = voice_id
            return iter([b"ID3"])

    class _FakeClient:
        def __init__(self, api_key: str) -> None:  # noqa: ARG002
            self.text_to_speech = _FakeTTS()

    fake_module = types.SimpleNamespace(ElevenLabs=_FakeClient)
    monkeypatch.setitem(sys.modules, "elevenlabs", fake_module)
    monkeypatch.setenv("ELEVENLABS_API_KEY", "fake-key")

    from jw_gen.providers.audio.elevenlabs import ElevenLabsProvider

    ElevenLabsProvider(work_dir=tmp_path).generate(GenerationRequest(prompt="x", kind="audio"))
    assert captured["voice_id"] == "EXAVITQu4vr4xnSDxMaL"
