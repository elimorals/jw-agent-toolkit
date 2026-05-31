"""In-process llama-cpp-python adapter (opt-in, grammar-native).

Use case: laptops without Ollama, or constrained-decoding inside CI
where you'd rather not run a daemon. Install with
`uv pip install -e packages/jw-core[grammar-local]`.
"""

from __future__ import annotations

import asyncio
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pydantic import BaseModel


class LlamaCppError(RuntimeError):
    pass


@dataclass
class LlamaCppAdapter:
    model_path: str | None = None
    n_ctx: int = 4096
    n_gpu_layers: int = 0
    _llm: Any = None  # cached Llama instance

    def __post_init__(self) -> None:
        if not self.model_path:
            self.model_path = os.environ.get("JW_LLAMA_CPP_MODEL") or None

    async def is_available(self) -> bool:
        try:
            import importlib

            importlib.import_module("llama_cpp")
        except ImportError:
            return False
        return bool(self.model_path and Path(self.model_path).exists())

    def _load(self) -> Any:
        if self._llm is not None:
            return self._llm
        if not self.model_path:
            raise LlamaCppError(
                "model_path is required (set JW_LLAMA_CPP_MODEL env or pass model_path=)"
            )
        try:
            from llama_cpp import Llama  # type: ignore[import-not-found]
        except ImportError as exc:
            raise LlamaCppError(
                "llama-cpp-python is not installed. "
                "Install with `uv pip install -e packages/jw-core[grammar-local]`."
            ) from exc
        self._llm = Llama(
            model_path=self.model_path, n_ctx=self.n_ctx, n_gpu_layers=self.n_gpu_layers
        )
        return self._llm

    async def generate(
        self,
        prompt: str,
        *,
        grammar: str | None = None,
        json_schema: type[BaseModel] | None = None,
        temperature: float = 0.3,
    ) -> str:
        if grammar is None and json_schema is None:
            raise LlamaCppError("pass grammar= or json_schema=")
        if grammar is None:
            assert json_schema is not None
            from jw_core.grammar.schemas import pydantic_to_gbnf

            grammar = pydantic_to_gbnf(json_schema)

        llm = self._load()

        try:
            from llama_cpp import LlamaGrammar  # type: ignore[import-not-found]
        except ImportError as exc:
            raise LlamaCppError("llama-cpp-python missing LlamaGrammar; upgrade.") from exc

        grammar_obj = LlamaGrammar.from_string(grammar)

        def _call() -> dict[str, Any]:
            return llm(
                prompt=prompt, grammar=grammar_obj, temperature=temperature, max_tokens=1024
            )

        out = await asyncio.to_thread(_call)
        text = out["choices"][0]["text"]
        # Validate output is JSON before returning — saves debugging time.
        json.loads(text)
        return str(text)
