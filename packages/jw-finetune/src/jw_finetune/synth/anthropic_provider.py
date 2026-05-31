"""Anthropic Claude provider for Q&A synthesis."""

from __future__ import annotations

import os

from jw_finetune.synth.provider import LLMRequest, LLMResponse


class AnthropicProvider:
    """Synchronous Anthropic provider.

    Lazy-imports the SDK so the package stays importable without the
    `[synth]` extra. The default model is a fast/cheap Haiku — overridable.
    """

    name = "anthropic"

    def __init__(
        self,
        model: str = "claude-haiku-4-5-20251001",
        api_key: str | None = None,
    ) -> None:
        try:
            import anthropic  # type: ignore[import-untyped]
        except ImportError as e:
            raise ImportError("anthropic SDK required: install with `--extra synth`") from e
        self.model = model
        self._client = anthropic.Anthropic(api_key=api_key or os.environ.get("ANTHROPIC_API_KEY"))

    def generate(self, req: LLMRequest) -> LLMResponse:
        resp = self._client.messages.create(
            model=self.model,
            max_tokens=req.max_tokens,
            temperature=req.temperature,
            system=req.system,
            messages=[{"role": "user", "content": req.user}],
        )
        text = "".join(b.text for b in resp.content if getattr(b, "type", None) == "text")
        return LLMResponse(
            text=text,
            provider=self.name,
            model=self.model,
            usage={
                "input_tokens": resp.usage.input_tokens,
                "output_tokens": resp.usage.output_tokens,
            },
        )
