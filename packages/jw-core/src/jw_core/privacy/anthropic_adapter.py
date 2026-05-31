"""Anthropic adapter for constrained decoding via tool-use.

Optional. Install with `uv pip install -e packages/jw-core[grammar-claude]`.
"""

from __future__ import annotations

import asyncio
import json
import os
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pydantic import BaseModel


class AnthropicAdapterError(RuntimeError):
    pass


@dataclass
class AnthropicAdapter:
    model: str = "claude-haiku-4-5-20251001"
    max_tokens: int = 1024

    async def is_available(self) -> bool:
        return bool(os.environ.get("ANTHROPIC_API_KEY"))

    async def generate(
        self,
        prompt: str,
        *,
        grammar: str | None = None,
        json_schema: type[BaseModel] | None = None,
        temperature: float = 0.3,
    ) -> str:
        if grammar is not None:
            raise NotImplementedError(
                "Anthropic adapter only accepts json_schema=. "
                "Raw GBNF grammars must go through the local Ollama or llama-cpp adapter."
            )
        if json_schema is None:
            raise AnthropicAdapterError("AnthropicAdapter.generate requires json_schema=")

        from anthropic import Anthropic  # type: ignore[import-not-found]

        client = Anthropic()
        tool_def = {
            "name": "emit_agent_result",
            "description": "Emit a strict AgentResult JSON object.",
            "input_schema": _strip_pydantic_keys(json_schema.model_json_schema()),
        }

        def _call() -> Any:
            return client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                temperature=temperature,
                tools=[tool_def],
                tool_choice={"type": "tool", "name": "emit_agent_result"},
                messages=[{"role": "user", "content": prompt}],
            )

        msg = await asyncio.to_thread(_call)
        for block in getattr(msg, "content", []):
            if getattr(block, "type", "") == "tool_use" and getattr(block, "input", None) is not None:
                return json.dumps(block.input, ensure_ascii=False)
        raise AnthropicAdapterError("anthropic response did not include tool_use block")


def _strip_pydantic_keys(schema: dict[str, Any]) -> dict[str, Any]:
    """Anthropic's JSON-schema validator rejects a few Pydantic-specific keys."""

    schema = dict(schema)
    schema.pop("$defs", None)
    schema.pop("definitions", None)
    return schema
