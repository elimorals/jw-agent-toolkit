from __future__ import annotations

import pytest
from jw_core.vision.vlm_providers import (
    JW_VLM_PROVIDER_ENV,
    FakeVLMProvider,
    get_default_provider,
)
from jw_core.vision.vlm_providers.factory import (
    DEFAULT_CHAIN,
    ProviderUnavailableError,
    build_provider,
)


def test_env_override_returns_named_provider(monkeypatch) -> None:
    monkeypatch.setenv(JW_VLM_PROVIDER_ENV, "fake")
    p = get_default_provider()
    assert isinstance(p, FakeVLMProvider)


def test_env_override_unknown_raises(monkeypatch) -> None:
    monkeypatch.setenv(JW_VLM_PROVIDER_ENV, "no-such-thing")
    with pytest.raises(ProviderUnavailableError):
        get_default_provider()


def test_default_chain_contains_all(monkeypatch) -> None:
    monkeypatch.delenv(JW_VLM_PROVIDER_ENV, raising=False)
    expected = {
        "qwen3vl_local",
        "qwen3vl_api",
        "claude_vision",
        "openai_vision",
        "tesseract_fallback",
    }
    assert expected.issubset(set(DEFAULT_CHAIN))


def test_get_default_picks_first_available(monkeypatch) -> None:
    monkeypatch.delenv(JW_VLM_PROVIDER_ENV, raising=False)

    # Force every real provider to "not available" by clearing env vars.
    for var in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "JW_QWEN3VL_API_KEY"):
        monkeypatch.delenv(var, raising=False)

    # When all real ones report unavailable, fallback should kick in; but the
    # fallback also depends on pytesseract. Patch the chain to inject Fake
    # explicitly at the end.
    from jw_core.vision.vlm_providers import factory as fmod

    fakes_only_chain = ["fake"]
    monkeypatch.setattr(fmod, "DEFAULT_CHAIN", fakes_only_chain)
    monkeypatch.setattr(
        fmod,
        "_REGISTRY_BUILDERS",
        {"fake": lambda: FakeVLMProvider()},
    )
    p = get_default_provider()
    assert isinstance(p, FakeVLMProvider)


def test_build_provider_unknown_name() -> None:
    with pytest.raises(ProviderUnavailableError):
        build_provider("does-not-exist")
