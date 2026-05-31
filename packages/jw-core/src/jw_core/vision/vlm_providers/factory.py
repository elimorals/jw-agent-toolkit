"""Factory + provider chain.

Resolution order:
  1. If env JW_VLM_PROVIDER is set, build that exact provider; if its
     is_available() is False, raise ProviderUnavailableError (do NOT fall back
     silently — explicit user choice).
  2. Else iterate DEFAULT_CHAIN; return the first whose is_available() is True.
  3. Else raise ProviderUnavailableError.

Every entry in the registry is a zero-arg factory that returns a fresh
provider instance. We construct lazily so optional SDKs are never imported
unless that provider is actually selected.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from jw_core.vision.vlm import VLMProvider


JW_VLM_PROVIDER_ENV = "JW_VLM_PROVIDER"


class ProviderUnavailableError(RuntimeError):
    """Raised when no provider is usable in the current environment."""


def _build_fake() -> VLMProvider:
    from jw_core.vision.vlm_providers.fakes import FakeVLMProvider

    return FakeVLMProvider()


def _build_claude() -> VLMProvider:
    from jw_core.vision.vlm_providers.claude_vision import ClaudeVisionProvider

    return ClaudeVisionProvider()


def _build_openai() -> VLMProvider:
    from jw_core.vision.vlm_providers.openai_vision import OpenAIVisionProvider

    return OpenAIVisionProvider()


def _build_qwen_api() -> VLMProvider:
    from jw_core.vision.vlm_providers.qwen3vl_api import Qwen3VLAPIProvider

    return Qwen3VLAPIProvider()


def _build_qwen_local() -> VLMProvider:
    from jw_core.vision.vlm_providers.qwen3vl_local import Qwen3VLProvider

    # default to mlx; users override target via JW_QWEN3VL_LOCAL_TARGET
    target = os.environ.get("JW_QWEN3VL_LOCAL_TARGET", "mlx")
    if target not in {"mlx", "nvidia", "cpu"}:
        target = "mlx"
    return Qwen3VLProvider(target=target)  # type: ignore[arg-type]


def _build_tesseract_fallback() -> VLMProvider:
    from jw_core.vision.vlm_providers.tesseract_fallback import (
        TesseractFallbackProvider,
    )

    return TesseractFallbackProvider()


_REGISTRY_BUILDERS: dict[str, Callable[[], VLMProvider]] = {
    "fake": _build_fake,
    "claude_vision": _build_claude,
    "openai_vision": _build_openai,
    "qwen3vl_api": _build_qwen_api,
    "qwen3vl_local": _build_qwen_local,
    "tesseract_fallback": _build_tesseract_fallback,
}


DEFAULT_CHAIN: list[str] = [
    "qwen3vl_local",
    "qwen3vl_api",
    "claude_vision",
    "openai_vision",
    "tesseract_fallback",
]


def build_provider(name: str) -> VLMProvider:
    """Construct a provider by registry name. Raise if unknown."""

    builder = _REGISTRY_BUILDERS.get(name)
    if builder is None:
        raise ProviderUnavailableError(f"unknown VLM provider {name!r}. Known: {sorted(_REGISTRY_BUILDERS)}")
    return builder()


def get_default_provider() -> VLMProvider:
    """Pick a provider per resolution rules above."""

    forced = os.environ.get(JW_VLM_PROVIDER_ENV)
    if forced:
        provider = build_provider(forced)
        if not provider.is_available():
            raise ProviderUnavailableError(
                f"{JW_VLM_PROVIDER_ENV}={forced!r} but provider reports unavailable. "
                "Install its extra, set its env vars, or change JW_VLM_PROVIDER."
            )
        return provider

    for name in DEFAULT_CHAIN:
        try:
            provider = build_provider(name)
        except Exception:  # noqa: BLE001
            continue
        try:
            if provider.is_available():
                return provider
        except Exception:  # noqa: BLE001
            continue

    raise ProviderUnavailableError(
        "no VLM provider available. Install one of: mlx-vlm, vllm, "
        "llama-cpp-python, anthropic, openai, pytesseract — or set "
        f"{JW_VLM_PROVIDER_ENV}=fake for tests."
    )
