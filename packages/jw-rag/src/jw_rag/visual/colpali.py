"""ColPali / ColQwen2 visual embedders.

Heavy deps (`colpali-engine`, `transformers`, `torch`, `mlx`, `mlx-vlm`) are
imported lazily inside the constructors. Importing this module is safe on any
machine — even with zero extras installed. Only the constructors and
`is_available()` touch hardware.

Hardware order (spec §"Hardware strategy"): NVIDIA first, MLX second, NO API
fallback, NO CPU fallback. When neither backend is available, the factory
raises `ConfigError` with the install commands.
"""

from __future__ import annotations

from typing import Literal

import numpy as np
from PIL import Image

from jw_rag.visual.errors import ConfigError
from jw_rag.visual.fakes import FakeColPaliEmbedder

Target = Literal["nvidia", "mlx"]


# ── Hardware probes (extracted so tests can monkey-patch them) ───────────


def _torch_cuda_available() -> bool:
    try:
        import torch  # type: ignore[import-not-found]
    except ImportError:
        return False
    if not torch.cuda.is_available():
        return False
    try:
        props = torch.cuda.get_device_properties(0)
    except (RuntimeError, AssertionError):
        return False
    return props.total_memory > 12_000_000_000  # ≥12 GB VRAM required


def _mlx_metal_available() -> bool:
    try:
        import mlx.core as mx  # type: ignore[import-not-found]
    except ImportError:
        return False
    try:
        return bool(mx.metal.is_available())
    except AttributeError:
        return False


# ── Real providers ───────────────────────────────────────────────────────


class _BaseRealEmbedder:
    """Shared scaffolding for ColPali/ColQwen2 real providers."""

    name: str = "base"
    dim: int = 128
    max_patches: int = 1030

    def __init__(self, target: Target = "nvidia") -> None:
        self.target = target
        self._model = None  # lazy-loaded

    @classmethod
    def is_available(cls, target: Target = "nvidia") -> bool:
        if target == "nvidia":
            return _torch_cuda_available()
        if target == "mlx":
            return _mlx_metal_available()
        return False

    def _ensure_model(self) -> None:
        raise NotImplementedError

    def embed_image(self, image: Image.Image) -> np.ndarray:
        self._ensure_model()
        return self._embed_image_impl(image)

    def embed_query(self, query: str) -> np.ndarray:
        self._ensure_model()
        return self._embed_query_impl(query)

    def _embed_image_impl(self, image: Image.Image) -> np.ndarray:
        raise NotImplementedError

    def _embed_query_impl(self, query: str) -> np.ndarray:
        raise NotImplementedError


class ColPaliEmbedder(_BaseRealEmbedder):
    """ColPali v1.2 (PaliGemma-based)."""

    name = "colpali-v1.2"
    dim = 128
    max_patches = 1030

    def _ensure_model(self) -> None:
        if self._model is not None:
            return
        try:
            import torch  # type: ignore[import-not-found]
            from colpali_engine.models import ColPali, ColPaliProcessor  # type: ignore[import-not-found]
        except ImportError as exc:
            raise ConfigError(
                f"colpali-engine / torch not installed: {exc}. Install with: uv sync --extra visual"
            ) from exc
        device = "cuda" if self.target == "nvidia" else "cpu"
        self._processor = ColPaliProcessor.from_pretrained("vidore/colpali-v1.2")
        self._model = ColPali.from_pretrained("vidore/colpali-v1.2", torch_dtype=torch.float16).to(device).eval()

    def _embed_image_impl(self, image: Image.Image) -> np.ndarray:
        import torch  # type: ignore[import-not-found]

        device = "cuda" if self.target == "nvidia" else "cpu"
        batch = self._processor.process_images([image]).to(device)
        with torch.no_grad():
            out = self._model(**batch)
        return out[0].to(torch.float16).cpu().numpy()

    def _embed_query_impl(self, query: str) -> np.ndarray:
        import torch  # type: ignore[import-not-found]

        device = "cuda" if self.target == "nvidia" else "cpu"
        batch = self._processor.process_queries([query]).to(device)
        with torch.no_grad():
            out = self._model(**batch)
        return out[0].to(torch.float16).cpu().numpy()


class ColQwen2Embedder(_BaseRealEmbedder):
    """ColQwen2 v0.1 (Qwen2-VL based, generally stronger than ColPali)."""

    name = "colqwen2-v0.1"
    dim = 128
    max_patches = 1030

    def _ensure_model(self) -> None:
        if self._model is not None:
            return
        try:
            import torch  # type: ignore[import-not-found]
            from colpali_engine.models import ColQwen2, ColQwen2Processor  # type: ignore[import-not-found]
        except ImportError as exc:
            raise ConfigError(
                f"colpali-engine / torch not installed: {exc}. Install with: uv sync --extra visual"
            ) from exc
        device = "cuda" if self.target == "nvidia" else "cpu"
        self._processor = ColQwen2Processor.from_pretrained("vidore/colqwen2-v0.1")
        self._model = ColQwen2.from_pretrained("vidore/colqwen2-v0.1", torch_dtype=torch.float16).to(device).eval()

    def _embed_image_impl(self, image: Image.Image) -> np.ndarray:
        import torch  # type: ignore[import-not-found]

        device = "cuda" if self.target == "nvidia" else "cpu"
        batch = self._processor.process_images([image]).to(device)
        with torch.no_grad():
            out = self._model(**batch)
        return out[0].to(torch.float16).cpu().numpy()

    def _embed_query_impl(self, query: str) -> np.ndarray:
        import torch  # type: ignore[import-not-found]

        device = "cuda" if self.target == "nvidia" else "cpu"
        batch = self._processor.process_queries([query]).to(device)
        with torch.no_grad():
            out = self._model(**batch)
        return out[0].to(torch.float16).cpu().numpy()


# ── Factory ──────────────────────────────────────────────────────────────

_PROVIDER_ORDER: list[Target] = ["nvidia", "mlx"]


def get_default_visual_embedder(*, prefer_fake: bool = False):
    """Return the first available visual embedder.

    Order: ColQwen2 > ColPali, NVIDIA > MLX. No CPU. No API.

    `prefer_fake=True` is a test-only escape hatch — production callers must
    never set it.

    Raises:
        ConfigError: when no GPU/MLX backend is reachable. Message includes
                     install hints and the env var to disable the subsystem.
    """
    if prefer_fake:
        return FakeColPaliEmbedder()

    for target in _PROVIDER_ORDER:
        for cls in (ColQwen2Embedder, ColPaliEmbedder):
            if cls.is_available(target=target):
                return cls(target=target)

    raise ConfigError(
        "No GPU available for ColPali/ColQwen2 visual embeddings.\n"
        "Options:\n"
        "  1. Install on a machine with NVIDIA GPU >=12GB VRAM:\n"
        "       uv sync --extra visual\n"
        "  2. Install on Apple Silicon (M2 or newer):\n"
        "       uv sync --extra visual-mlx\n"
        "  3. Disable the visual module entirely:\n"
        "       export JW_VISUAL_ENABLED=0\n"
        "For tests, use FakeColPaliEmbedder (jw_rag.visual.fakes).\n"
    )
