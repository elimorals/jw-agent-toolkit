"""Ollama local provider for Q&A synthesis."""

from __future__ import annotations

from jw_finetune.synth.provider import LLMRequest, LLMResponse


class OllamaProvider:
    """Synchronous Ollama provider — zero cost, fully local."""

    name = "ollama"

    def __init__(
        self,
        model: str = "llama3.1:8b",
        host: str = "http://localhost:11434",
    ) -> None:
        try:
            import ollama  # type: ignore[import-untyped]
        except ImportError as e:
            raise ImportError(
                "ollama SDK required: install with `--extra synth`"
            ) from e
        self.model = model
        self._client = ollama.Client(host=host)

    def generate(self, req: LLMRequest) -> LLMResponse:
        resp = self._client.chat(
            model=self.model,
            messages=[
                {"role": "system", "content": req.system},
                {"role": "user", "content": req.user},
            ],
            options={
                "temperature": req.temperature,
                "num_predict": req.max_tokens,
            },
        )
        text = resp["message"]["content"]
        return LLMResponse(
            text=text,
            provider=self.name,
            model=self.model,
            usage={
                "input_tokens": int(resp.get("prompt_eval_count", 0)),
                "output_tokens": int(resp.get("eval_count", 0)),
            },
        )
