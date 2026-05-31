"""Qwen3VLProvider — local execution.

Three backends, all behind a `_Backend` protocol. The provider iterates the
list and uses the first one whose `available()` returns True. Each backend
lazy-imports its SDK so missing extras never break import.

Env:
  JW_QWEN3VL_LOCAL_MODEL  — model id; defaults per backend.
"""

from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from jw_core.vision.vlm import (
    DEFAULT_VLM_PROMPT,
    CostHint,
    StructuredPage,
    Target,
    parse_structured_page_json,
)


class _Backend(Protocol):
    name: str

    def available(self) -> bool: ...

    def generate(self, image: Path | bytes, prompt: str) -> str: ...


def _materialize_bytes(buf: bytes) -> Path:
    f = tempfile.NamedTemporaryFile(prefix="jwvlm-", suffix=".png", delete=False)
    f.write(buf)
    f.close()
    return Path(f.name)


class _MLXBackend:
    name = "mlx-vlm"

    def __init__(self, model: str | None = None) -> None:
        self.model = (
            model
            or os.environ.get("JW_QWEN3VL_LOCAL_MODEL")
            or "mlx-community/Qwen3-VL-2B-Instruct-4bit"
        )

    def available(self) -> bool:
        try:
            import mlx_vlm  # noqa: F401
        except ImportError:
            return False
        return True

    def generate(self, image: Path | bytes, prompt: str) -> str:
        from mlx_vlm import generate, load  # type: ignore[import-not-found]

        model_obj, processor = load(self.model)
        path = image if isinstance(image, Path) else _materialize_bytes(image)
        return generate(model_obj, processor, prompt=prompt, image=str(path), max_tokens=2048)


class _VLLMBackend:
    name = "vllm"

    def __init__(self, model: str | None = None) -> None:
        self.model = (
            model
            or os.environ.get("JW_QWEN3VL_LOCAL_MODEL")
            or "Qwen/Qwen3-VL-8B-Instruct"
        )

    def available(self) -> bool:
        try:
            import vllm  # noqa: F401
        except ImportError:
            return False
        return True

    def generate(self, image: Path | bytes, prompt: str) -> str:
        from vllm import LLM, SamplingParams  # type: ignore[import-not-found]

        llm = LLM(model=self.model, dtype="bfloat16")
        path = image if isinstance(image, Path) else _materialize_bytes(image)
        result = llm.generate(
            [{"prompt": prompt, "multi_modal_data": {"image": str(path)}}],
            sampling_params=SamplingParams(max_tokens=2048, temperature=0.0),
        )
        return result[0].outputs[0].text


class _GGUFBackend:
    name = "llama-cpp-python"

    def __init__(self, model_path: str | None = None) -> None:
        self.model_path = (
            model_path
            or os.environ.get("JW_QWEN3VL_LOCAL_MODEL")
            or os.path.expanduser("~/.cache/qwen3vl-2b-q4_k_m.gguf")
        )

    def available(self) -> bool:
        try:
            import llama_cpp  # noqa: F401
        except ImportError:
            return False
        return os.path.exists(self.model_path)

    def generate(self, image: Path | bytes, prompt: str) -> str:
        from llama_cpp import Llama  # type: ignore[import-not-found]

        llm = Llama(model_path=self.model_path, n_ctx=4096, logits_all=False)
        path = image if isinstance(image, Path) else _materialize_bytes(image)
        resp = llm.create_chat_completion(
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "image_url", "image_url": {"url": f"file://{path}"}},
                        {"type": "text", "text": prompt},
                    ],
                }
            ],
            max_tokens=2048,
        )
        return resp["choices"][0]["message"]["content"]


def _default_backends_for(target: Target) -> list[_Backend]:
    if target == "mlx":
        return [_MLXBackend()]
    if target == "nvidia":
        return [_VLLMBackend()]
    if target == "cpu":
        return [_GGUFBackend()]
    return [_MLXBackend(), _VLLMBackend(), _GGUFBackend()]


@dataclass
class Qwen3VLProvider:
    target: Target = "mlx"
    backends: list[_Backend] | None = None
    name: str = field(default="qwen3vl_local", init=False)

    def _backends(self) -> list[_Backend]:
        if self.backends is not None:
            return self.backends
        return _default_backends_for(self.target)

    def _pick(self) -> _Backend | None:
        for b in self._backends():
            if b.available():
                return b
        return None

    def is_available(self) -> bool:
        return self._pick() is not None

    def cost_estimate(self, image: Path | bytes) -> CostHint:  # noqa: ARG002
        return CostHint(cents_estimate=0.0, latency_ms_estimate=6000, network=False)

    def extract_structured(
        self,
        image: Path | bytes,
        prompt: str | None = None,
        *,
        language: str = "en",
    ) -> StructuredPage:
        backend = self._pick()
        if backend is None:
            raise RuntimeError(
                "Qwen3VLProvider unavailable: install one of mlx-vlm / vllm / llama-cpp-python."
            )
        prompt_text = (prompt or DEFAULT_VLM_PROMPT) + f"\nLanguage hint: {language}\n"
        raw_text = backend.generate(image, prompt_text)
        blocks, lang = parse_structured_page_json(raw_text)
        return StructuredPage(
            blocks=blocks,
            source_image=str(image) if isinstance(image, Path) else None,
            provider_name=self.name,
            target=self.target,
            raw_text_fallback=raw_text,
            language_detected=lang or language,
        )
