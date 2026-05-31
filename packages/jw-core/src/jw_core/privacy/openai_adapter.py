"""OpenAI adapter for constrained decoding via response_format=json_schema."""

from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pydantic import BaseModel


class OpenAIAdapterError(RuntimeError):
    pass


@dataclass
class OpenAIAdapter:
    model: str = "gpt-4o-mini"
    max_tokens: int = 1024

    async def is_available(self) -> bool:
        return bool(os.environ.get("OPENAI_API_KEY"))

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
                "OpenAI adapter only accepts json_schema=. Use the Ollama or llama-cpp adapter for raw GBNF grammars."
            )
        if json_schema is None:
            raise OpenAIAdapterError("OpenAIAdapter.generate requires json_schema=")

        from openai import OpenAI  # type: ignore[import-not-found]

        client = OpenAI()
        schema = json_schema.model_json_schema()
        response_format = {
            "type": "json_schema",
            "json_schema": {
                "name": json_schema.__name__,
                "strict": True,
                "schema": _harden_schema_for_openai(schema),
            },
        }

        def _call() -> Any:
            return client.chat.completions.create(
                model=self.model,
                max_tokens=self.max_tokens,
                temperature=temperature,
                response_format=response_format,
                messages=[{"role": "user", "content": prompt}],
            )

        resp = await asyncio.to_thread(_call)
        return resp.choices[0].message.content or ""


def _harden_schema_for_openai(schema: dict[str, Any]) -> dict[str, Any]:
    """OpenAI's strict JSON-schema mode requires every object property to be in `required`."""

    if schema.get("type") == "object":
        props = schema.get("properties", {})
        schema = dict(schema)
        schema["required"] = list(props.keys())
        schema["additionalProperties"] = False
        schema["properties"] = {k: _harden_schema_for_openai(v) for k, v in props.items()}
    if schema.get("type") == "array" and "items" in schema:
        schema = dict(schema)
        schema["items"] = _harden_schema_for_openai(schema["items"])
    return schema
