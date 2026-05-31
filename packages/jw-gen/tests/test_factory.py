from __future__ import annotations

import pytest

from jw_gen.factory import NoProviderAvailable, get_provider
from jw_gen.providers.fakes import (
    FakeAudioProvider,
    FakeImageProvider,
    FakeVideoProvider,
)


def test_get_provider_image_returns_fake_when_no_api_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    for var in (
        "GEMINI_API_KEY",
        "OPENAI_API_KEY",
        "REPLICATE_API_TOKEN",
        "RECRAFT_API_KEY",
    ):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("JW_GEN_IMAGE_PROVIDER", "fake")
    p = get_provider("image")
    assert isinstance(p, FakeImageProvider)


def test_get_provider_audio_returns_fake_explicit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JW_GEN_AUDIO_PROVIDER", "fake")
    p = get_provider("audio")
    assert isinstance(p, FakeAudioProvider)


def test_get_provider_video_returns_fake_explicit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JW_GEN_VIDEO_PROVIDER", "fake")
    p = get_provider("video")
    assert isinstance(p, FakeVideoProvider)


def test_get_provider_unknown_name_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JW_GEN_IMAGE_PROVIDER", "definitely-not-real")
    # Also clear API keys so the fallback chain has nothing.
    for var in (
        "GEMINI_API_KEY",
        "OPENAI_API_KEY",
        "REPLICATE_API_TOKEN",
        "RECRAFT_API_KEY",
    ):
        monkeypatch.delenv(var, raising=False)
    with pytest.raises(NoProviderAvailable):
        # Explicitly disable the fake floor so unknown names actually fail.
        get_provider("image", allow_fake_fallback=False)


def test_get_provider_explicit_name_wins(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JW_GEN_IMAGE_PROVIDER", "nanobanana")
    # Even if env is set, explicit kwarg wins.
    p = get_provider("image", provider="fake")
    assert isinstance(p, FakeImageProvider)
