"""Ollama adapter (optional local LLM provider).

VISION.md: "Modelo LLM local (Ollama/Llama) opcional — Claude no es opción
para todos".

We don't add `ollama` as a hard dependency. If the user has Ollama
running on `http://localhost:11434` we talk to it via plain HTTP.

Use:

    adapter = OllamaAdapter(model="llama3.1")
    if adapter.is_available():
        text = await adapter.generate("Summarise: ...")

The adapter purposely doesn't implement the full Anthropic-style streaming
API — it's just enough to swap in for ad-hoc summarisation / re-ranking.
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from dataclasses import dataclass

import httpx


class OllamaError(RuntimeError):
    pass


@dataclass
class OllamaAdapter:
    model: str = "llama3.1"
    host: str = ""

    def __post_init__(self) -> None:
        self.host = self.host or os.getenv("JW_OLLAMA_HOST", "http://localhost:11434")

    async def is_available(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=2.0) as c:
                resp = await c.get(f"{self.host}/api/tags")
                resp.raise_for_status()
                return True
        except Exception:
            return False

    async def generate(self, prompt: str, *, temperature: float = 0.3) -> str:
        try:
            async with httpx.AsyncClient(timeout=60.0) as c:
                resp = await c.post(
                    f"{self.host}/api/generate",
                    json={
                        "model": self.model,
                        "prompt": prompt,
                        "stream": False,
                        "options": {"temperature": temperature},
                    },
                )
                resp.raise_for_status()
        except httpx.HTTPError as e:
            raise OllamaError(f"Ollama request failed: {e}") from e
        data = resp.json()
        return data.get("response", "")

    async def generate_stream(self, prompt: str, *, temperature: float = 0.3) -> AsyncIterator[str]:
        """Yield chunks of generated text. Caller joins as needed."""
        try:
            async with (
                httpx.AsyncClient(timeout=120.0) as c,
                c.stream(
                    "POST",
                    f"{self.host}/api/generate",
                    json={
                        "model": self.model,
                        "prompt": prompt,
                        "stream": True,
                        "options": {"temperature": temperature},
                    },
                ) as resp,
            ):
                resp.raise_for_status()
                import json as _json

                async for line in resp.aiter_lines():
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        payload = _json.loads(line)
                    except Exception:
                        continue
                    chunk = payload.get("response", "")
                    if chunk:
                        yield chunk
                    if payload.get("done"):
                        return
        except httpx.HTTPError as e:
            raise OllamaError(f"Ollama stream failed: {e}") from e


async def ollama_available(host: str | None = None) -> bool:
    return await OllamaAdapter(host=host or "").is_available()
