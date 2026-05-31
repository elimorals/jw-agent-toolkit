"""Client abstraction for consuming a fine-tuned jw-finetune model.

The fine-tuned model can be served in two ways:

  * **Ollama** (after `jw-finetune export --format gguf` + `ollama create`).
    This is the recommended path: it's fast, stays local, and doesn't
    require the heavy Unsloth stack at inference time.

  * **Direct (Unsloth/transformers)**. Heavier but useful when you don't
    want to convert to GGUF first (e.g. quick smoke test from a freshly
    trained checkpoint).

Both backends implement the `FinetunedModelClient` Protocol so callers can
swap them transparently. Each is opt-in via the relevant extra:
`jw-agents[ollama]` or `jw-agents[unsloth]`.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class GenerateRequest:
    prompt: str
    system: str = ""
    max_new_tokens: int = 512
    temperature: float = 0.4
    language: str = "es"


@dataclass(frozen=True)
class GenerateResponse:
    text: str
    backend: str
    model: str
    usage: dict[str, int]


class FinetunedModelClient(Protocol):
    backend: str
    model: str

    def generate(self, req: GenerateRequest) -> GenerateResponse: ...


# ---------------------------------------------------------------------------
# Ollama backend
# ---------------------------------------------------------------------------


class OllamaFinetunedClient:
    """Consume a fine-tuned model served by a local Ollama install.

    Typical flow:
        jw-finetune export --format gguf --quant Q4_K_M --out ./mi-modelo
        cd mi-modelo && cat > Modelfile <<EOF
        FROM ./model-Q4_K_M.gguf
        SYSTEM "Eres un asistente JW respetuoso."
        EOF
        ollama create mi-jw -f Modelfile
        # Now in Python:
        client = OllamaFinetunedClient(model="mi-jw")
        resp = client.generate(GenerateRequest(prompt="¿Qué es el Reino?"))
    """

    backend = "ollama"

    def __init__(
        self,
        model: str = "mi-jw",
        host: str = "http://localhost:11434",
    ) -> None:
        try:
            import ollama  # type: ignore[import-untyped]
        except ImportError as e:
            raise ImportError("ollama SDK required: pip install ollama") from e
        self.model = model
        self._client = ollama.Client(host=host)

    def generate(self, req: GenerateRequest) -> GenerateResponse:
        msgs: list[dict[str, str]] = []
        if req.system:
            msgs.append({"role": "system", "content": req.system})
        msgs.append({"role": "user", "content": req.prompt})
        resp = self._client.chat(
            model=self.model,
            messages=msgs,
            options={
                "temperature": req.temperature,
                "num_predict": req.max_new_tokens,
            },
        )
        return GenerateResponse(
            text=resp["message"]["content"],
            backend=self.backend,
            model=self.model,
            usage={
                "input_tokens": int(resp.get("prompt_eval_count", 0)),
                "output_tokens": int(resp.get("eval_count", 0)),
            },
        )


# ---------------------------------------------------------------------------
# Unsloth direct backend
# ---------------------------------------------------------------------------


class UnslothFinetunedClient:
    """Consume a fine-tuned checkpoint directly via Unsloth (GPU required)."""

    backend = "unsloth"

    def __init__(
        self,
        checkpoint_dir: Path | str,
        *,
        max_seq_length: int = 2048,
    ) -> None:
        try:
            from unsloth import FastLanguageModel  # type: ignore[import-untyped]
        except ImportError as e:
            raise ImportError("unsloth required: install with the [unsloth] extra") from e
        self._FLM = FastLanguageModel
        self.checkpoint_dir = Path(checkpoint_dir)
        self.model_name = str(checkpoint_dir)
        self.model = self.model_name
        self._max_seq_length = max_seq_length
        self._loaded = False
        self._model = None
        self._tokenizer = None

    def _load(self) -> None:
        if self._loaded:
            return
        self._model, self._tokenizer = self._FLM.from_pretrained(
            model_name=self.model_name,
            max_seq_length=self._max_seq_length,
            load_in_4bit=True,
            dtype=None,
        )
        self._FLM.for_inference(self._model)
        self._loaded = True

    def generate(self, req: GenerateRequest) -> GenerateResponse:
        self._load()
        messages = []
        if req.system:
            messages.append({"role": "system", "content": req.system})
        messages.append({"role": "user", "content": req.prompt})
        inputs = self._tokenizer.apply_chat_template(  # type: ignore[union-attr]
            messages,
            return_tensors="pt",
            add_generation_prompt=True,
        ).to(self._model.device)  # type: ignore[union-attr]
        out = self._model.generate(  # type: ignore[union-attr]
            inputs,
            max_new_tokens=req.max_new_tokens,
            do_sample=req.temperature > 0,
            temperature=req.temperature,
        )
        text = self._tokenizer.decode(  # type: ignore[union-attr]
            out[0][inputs.shape[1] :],
            skip_special_tokens=True,
        )
        return GenerateResponse(
            text=text,
            backend=self.backend,
            model=self.model_name,
            usage={
                "input_tokens": int(inputs.shape[1]),
                "output_tokens": int(out.shape[1] - inputs.shape[1]),
            },
        )


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def build_client(
    backend: str = "ollama",
    *,
    model: str = "mi-jw",
    checkpoint_dir: Path | str | None = None,
    host: str = "http://localhost:11434",
) -> FinetunedModelClient:
    """Convenience factory: build the right client by name."""
    if backend == "ollama":
        return OllamaFinetunedClient(model=model, host=host)
    if backend == "unsloth":
        if checkpoint_dir is None:
            raise ValueError("checkpoint_dir required for 'unsloth' backend")
        return UnslothFinetunedClient(checkpoint_dir=checkpoint_dir)
    raise ValueError(f"Unknown backend: {backend!r}")
