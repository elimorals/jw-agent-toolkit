"""LLM provider factory for the meta-orchestrator (Fase 65 post-MVP).

Bridges the meta planner's `acomplete(prompt: str) -> str` async API to
the existing sync `LLMProvider.generate(LLMRequest) -> LLMResponse`
contract from `jw_finetune.synth.provider`.

Env-driven selection via `JW_META_LLM`:
  - `fake` (default) -> deterministic empty plan
  - `anthropic` / `claude` -> `AnthropicProvider`
  - `ollama` -> `OllamaProvider`

Additional env knobs:
  - `JW_META_MODEL` overrides the per-backend model id
  - `JW_META_OLLAMA_HOST` overrides the Ollama URL (default
    `http://localhost:11434`)
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import Any

logger = logging.getLogger(__name__)


# A short, neutral system prompt that nudges the LLM to return JSON only.
_SYSTEM_PROMPT = (
    "You translate the planning instructions you receive into a single, "
    "strict JSON object matching the schema described in the user message. "
    "Respond with the JSON object only — no Markdown fences, no prose."
)


class _FakeAcompletionLLM:
    """Default fake: returns a deterministic empty plan for offline tests."""

    name = "fake"

    async def acomplete(self, prompt: str) -> str:  # noqa: ARG002
        return json.dumps({"goal": "", "language": "es", "steps": []})


class _SyncProviderAcompletionAdapter:
    """Wraps a sync `LLMProvider.generate(...)` into the async
    `acomplete(prompt)` shape expected by `Planner`.

    We run the sync call inside `asyncio.to_thread` so that long network
    waits do not block the event loop.
    """

    def __init__(self, provider: Any) -> None:
        self._provider = provider

    @property
    def name(self) -> str:
        return getattr(self._provider, "name", "unknown")

    async def acomplete(self, prompt: str) -> str:
        from jw_finetune.synth.provider import LLMRequest

        req = LLMRequest(system=_SYSTEM_PROMPT, user=prompt)
        response = await asyncio.to_thread(self._provider.generate, req)
        return getattr(response, "text", "")


def _build_anthropic() -> Any:
    """Return an `AnthropicProvider`, honoring `JW_META_MODEL`."""
    from jw_finetune.synth.anthropic_provider import AnthropicProvider

    model = os.environ.get("JW_META_MODEL")
    if model:
        return AnthropicProvider(model=model)
    return AnthropicProvider()


def _build_ollama() -> Any:
    """Return an `OllamaProvider`, honoring `JW_META_MODEL` / `JW_META_OLLAMA_HOST`."""
    from jw_finetune.synth.ollama_provider import OllamaProvider

    model = os.environ.get("JW_META_MODEL", "llama3.1:8b")
    host = os.environ.get("JW_META_OLLAMA_HOST", "http://localhost:11434")
    return OllamaProvider(model=model, host=host)


def build_llm_from_env() -> Any:
    """Construct an async-shaped LLM from `JW_META_LLM`.

    Returns an object exposing `acomplete(prompt: str) -> str`.
    Failure modes (missing dependency, missing API key) degrade to the
    fake provider with a single warning so the orchestrator never crashes
    on boot. Misconfiguration shows up in the warning log, not in the user
    request path.
    """

    backend = os.environ.get("JW_META_LLM", "fake").lower()
    if backend in ("", "fake"):
        return _FakeAcompletionLLM()

    if backend in ("anthropic", "claude"):
        try:
            return _SyncProviderAcompletionAdapter(_build_anthropic())
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "meta: AnthropicProvider unavailable (%s); using fake LLM.",
                exc,
            )
            return _FakeAcompletionLLM()

    if backend == "ollama":
        try:
            return _SyncProviderAcompletionAdapter(_build_ollama())
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "meta: OllamaProvider unavailable (%s); using fake LLM.",
                exc,
            )
            return _FakeAcompletionLLM()

    logger.warning("meta: unknown backend %r; using fake LLM.", backend)
    return _FakeAcompletionLLM()
