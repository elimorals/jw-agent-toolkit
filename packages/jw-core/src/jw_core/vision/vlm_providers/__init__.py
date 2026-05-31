"""Concrete VLM providers (lazy-import SDKs internally).

Public re-exports:
    FakeVLMProvider, ClaudeVisionProvider, OpenAIVisionProvider,
    Qwen3VLAPIProvider, Qwen3VLProvider, TesseractFallbackProvider,
    get_default_provider, build_provider, JW_VLM_PROVIDER_ENV.
"""

from jw_core.vision.vlm_providers.factory import (
    JW_VLM_PROVIDER_ENV,
    build_provider,
    get_default_provider,
)
from jw_core.vision.vlm_providers.fakes import FakeVLMProvider

__all__ = [
    "JW_VLM_PROVIDER_ENV",
    "FakeVLMProvider",
    "build_provider",
    "get_default_provider",
]
