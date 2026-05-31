"""Provider factory for constrained decoding."""

from __future__ import annotations

import asyncio
import os
import sys
from typing import Literal, Protocol, runtime_checkable

from pydantic import BaseModel


@runtime_checkable
class ConstrainedCaller(Protocol):
    """The unified interface adapters must satisfy."""

    async def is_available(self) -> bool: ...

    async def generate(
        self,
        prompt: str,
        *,
        grammar: str | None = None,
        json_schema: type[BaseModel] | None = None,
        temperature: float = 0.3,
    ) -> str: ...


_KNOWN = {"ollama", "anthropic", "openai", "fake", "llama-cpp"}


def get_default_constrained_caller(
    provider: Literal["ollama", "anthropic", "openai", "fake", "llama-cpp"] | None = None,
    *,
    warn_on_fallback: bool = True,
) -> ConstrainedCaller:
    """Resolve the best available constrained-decoding caller.

    Resolution order:
        explicit `provider=` arg → `JW_LLM_PROVIDER` env →
        live Ollama probe → ANTHROPIC_API_KEY → OPENAI_API_KEY →
        FakeConstrainedCaller (always succeeds, prints stderr warning).
    """

    name = provider or os.environ.get("JW_LLM_PROVIDER")
    if name is not None and name not in _KNOWN:
        raise ValueError(f"unknown JW_LLM_PROVIDER={name!r} (expected one of {_KNOWN})")

    if name == "fake":
        from jw_core.grammar.fake import FakeConstrainedCaller

        return FakeConstrainedCaller()

    if name == "ollama" or name is None:
        try:
            from jw_core.privacy.ollama_adapter import OllamaAdapter

            adapter = OllamaAdapter()
            if asyncio.run(adapter.is_available()):
                return adapter  # type: ignore[return-value]
        except Exception:
            pass

    if name == "anthropic" or (name is None and os.environ.get("ANTHROPIC_API_KEY")):
        try:
            from jw_core.privacy.anthropic_adapter import AnthropicAdapter

            return AnthropicAdapter()  # type: ignore[return-value]
        except Exception:
            pass

    if name == "openai" or (name is None and os.environ.get("OPENAI_API_KEY")):
        try:
            from jw_core.privacy.openai_adapter import OpenAIAdapter

            return OpenAIAdapter()  # type: ignore[return-value]
        except Exception:
            pass

    if name == "llama-cpp":
        try:
            from jw_core.privacy.llama_cpp_adapter import LlamaCppAdapter

            return LlamaCppAdapter()  # type: ignore[return-value]
        except Exception as exc:
            raise RuntimeError(f"llama-cpp adapter unavailable: {exc}") from exc

    from jw_core.grammar.fake import FakeConstrainedCaller

    if warn_on_fallback:
        print(
            "jw_core.grammar.factory: no LLM provider available, "
            "falling back to FakeConstrainedCaller (test-only).",
            file=sys.stderr,
        )
    return FakeConstrainedCaller()
