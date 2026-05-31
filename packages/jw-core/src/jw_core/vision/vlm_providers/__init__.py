"""Concrete VLM providers (lazy-import SDKs internally).

Public re-exports:
    FakeVLMProvider, ClaudeVisionProvider, OpenAIVisionProvider,
    Qwen3VLAPIProvider, Qwen3VLProvider, TesseractFallbackProvider,
    get_default_provider, build_provider, JW_VLM_PROVIDER_ENV.

Each symbol is re-exported as soon as its module exists. We keep the module
import graph robust against partial scaffolds during TDD by guarding the
factory import.
"""

from jw_core.vision.vlm_providers.fakes import FakeVLMProvider

try:  # factory lands in Task 9; keep import safe until then
    from jw_core.vision.vlm_providers.factory import (
        JW_VLM_PROVIDER_ENV,
        build_provider,
        get_default_provider,
    )
except ImportError:  # pragma: no cover - only during early scaffolding
    JW_VLM_PROVIDER_ENV = "JW_VLM_PROVIDER"  # type: ignore[assignment]
    build_provider = None  # type: ignore[assignment]
    get_default_provider = None  # type: ignore[assignment]

__all__ = [
    "JW_VLM_PROVIDER_ENV",
    "FakeVLMProvider",
    "build_provider",
    "get_default_provider",
]
