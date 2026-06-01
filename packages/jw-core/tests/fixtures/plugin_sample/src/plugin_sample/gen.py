"""Gen provider stub."""

from __future__ import annotations


class SampleGen:
    name = "plugin_sample_gen"

    def is_available(self) -> bool:
        return True

    def generate(self, prompt: str, *, max_tokens: int = 128) -> str:
        return f"plugin_sample_gen[{max_tokens}]: {prompt}"
