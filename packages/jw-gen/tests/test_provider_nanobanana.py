"""Offline unit tests for NanoBanana adapter.

The SDK (`google.genai`) is monkeypatched into sys.modules with a fake
that captures call args. No network, no real key required.
"""

from __future__ import annotations

import sys
import types
from pathlib import Path

import pytest

from jw_gen.models import GenerationRequest


def test_is_available_false_when_no_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    from jw_gen.providers.image.nanobanana import NanoBananaProvider

    assert NanoBananaProvider().is_available() is False


def test_is_available_false_when_sdk_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "fake-key")
    monkeypatch.setitem(sys.modules, "google.genai", None)
    from jw_gen.providers.image.nanobanana import NanoBananaProvider

    assert NanoBananaProvider().is_available() is False


def test_cost_estimate_is_constant(tmp_path: Path) -> None:
    from jw_gen.providers.image.nanobanana import NanoBananaProvider

    p = NanoBananaProvider(work_dir=tmp_path)
    hint = p.cost_estimate(GenerationRequest(prompt="x", kind="image"))
    assert hint.usd > 0
    assert hint.time_s > 0


def test_generate_calls_sdk_and_writes_png(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    captured: dict = {}

    class _FakeImage:
        image_bytes = b"\x89PNG\r\n\x1a\nFAKE"

    class _FakeGen:
        def __init__(self) -> None:
            self.generated_images = [types.SimpleNamespace(image=_FakeImage())]

    class _FakeModels:
        def generate_images(self, *, model: str, prompt: str, number_of_images: int):
            captured["model"] = model
            captured["prompt"] = prompt
            captured["n"] = number_of_images
            return _FakeGen()

    class _FakeClient:
        def __init__(self, api_key: str) -> None:
            captured["api_key"] = api_key
            self.models = _FakeModels()

    fake_genai = types.SimpleNamespace(Client=_FakeClient)
    fake_google = types.ModuleType("google")
    fake_google.genai = fake_genai  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "google", fake_google)
    monkeypatch.setitem(sys.modules, "google.genai", fake_genai)
    monkeypatch.setenv("GEMINI_API_KEY", "fake-key")

    from jw_gen.providers.image.nanobanana import NanoBananaProvider

    p = NanoBananaProvider(work_dir=tmp_path)
    out = p.generate(GenerationRequest(prompt="paisaje sereno", kind="image"))

    assert out.exists()
    assert out.read_bytes().startswith(b"\x89PNG")
    assert captured["model"] == "imagen-4.0-generate-001"
    assert captured["prompt"] == "paisaje sereno"
    assert captured["api_key"] == "fake-key"
