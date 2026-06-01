"""VLM stub."""

from __future__ import annotations


class SampleVLM:
    name = "plugin_sample_vlm"

    def is_available(self) -> bool:
        return True

    def describe(self, image_bytes: bytes, *, language: str = "en") -> str:
        return f"plugin_sample_vlm[{language}] len={len(image_bytes)}"
