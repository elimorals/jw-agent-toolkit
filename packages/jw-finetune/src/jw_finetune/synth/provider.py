"""LLM Provider Protocol — the seam between the orchestrator and any backend.

Implementations only need to expose `name`, `model`, and a synchronous
`generate(LLMRequest) -> LLMResponse`. Async could be added later; the
orchestrator is currently synchronous and runs one chunk at a time.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class LLMRequest:
    system: str
    user: str
    max_tokens: int = 1024
    temperature: float = 0.5


@dataclass(frozen=True)
class LLMResponse:
    text: str
    provider: str
    model: str
    usage: dict[str, int]  # {"input_tokens": N, "output_tokens": M}


class LLMProvider(Protocol):
    name: str
    model: str

    def generate(self, req: LLMRequest) -> LLMResponse: ...
