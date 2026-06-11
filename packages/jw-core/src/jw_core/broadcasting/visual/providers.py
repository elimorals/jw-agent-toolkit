"""VLM and CLIP provider protocols + deterministic Fakes (Fase 69).

The real providers (Llava-1.6 / Qwen-VL / Florence-2 for VLM,
ViT-B/32 CLIP for embeddings) ship as optional extras and may live in
isolated polyglot venvs (F53). The Fakes here are deterministic and
import-free so tests and the FakeVLM-default install work everywhere.
"""

from __future__ import annotations

import hashlib
import logging
from typing import Any, Protocol, runtime_checkable

logger = logging.getLogger(__name__)


@runtime_checkable
class VLMProvider(Protocol):
    """Vision-language provider that captions a PIL.Image (or compatible)."""

    name: str
    requires_gpu: bool

    def caption(self, image: Any, language: str = "en") -> str: ...


@runtime_checkable
class CLIPEncoder(Protocol):
    """Text+image encoder producing fixed-dim embeddings."""

    name: str
    embedding_dim: int

    def encode_image(self, image: Any) -> list[float]: ...
    def encode_text(self, text: str) -> list[float]: ...


# ---- Fake implementations ----------------------------------------------


def _hash_to_floats(payload: bytes, dim: int) -> list[float]:
    """Deterministic [-1, 1] floats derived from `payload`."""

    out: list[float] = []
    seed = hashlib.sha256(payload).digest()
    i = 0
    while len(out) < dim:
        b = seed[i % len(seed)]
        # Map 0..255 -> -1..1
        out.append((b - 128) / 128.0)
        i += 1
    return out


def _normalize(v: list[float]) -> list[float]:
    s = sum(x * x for x in v) ** 0.5
    if s == 0:
        return v
    return [x / s for x in v]


class FakeVLMProvider:
    """Deterministic caption tied to image bytes + language."""

    name = "fake-vlm"
    requires_gpu = False

    def caption(self, image: Any, language: str = "en") -> str:
        payload = self._to_bytes(image)
        digest = hashlib.sha256(payload + language.encode()).hexdigest()
        # Stable short caption so tests can assert
        return f"image-{digest[:8]} ({language})"

    @staticmethod
    def _to_bytes(image: Any) -> bytes:
        if isinstance(image, bytes):
            return image
        if hasattr(image, "tobytes"):
            try:
                return image.tobytes()  # PIL.Image
            except Exception:
                return repr(image).encode()
        return repr(image).encode()


class FakeCLIPEncoder:
    """Deterministic image/text embeddings for offline tests."""

    name = "fake-clip"

    def __init__(self, embedding_dim: int = 64) -> None:
        self.embedding_dim = embedding_dim

    def encode_image(self, image: Any) -> list[float]:
        return _normalize(
            _hash_to_floats(self._to_bytes(image), self.embedding_dim)
        )

    def encode_text(self, text: str) -> list[float]:
        return _normalize(
            _hash_to_floats(text.encode(), self.embedding_dim)
        )

    @staticmethod
    def _to_bytes(image: Any) -> bytes:
        if isinstance(image, bytes):
            return image
        if hasattr(image, "tobytes"):
            try:
                return image.tobytes()
            except Exception:
                return repr(image).encode()
        return repr(image).encode()
