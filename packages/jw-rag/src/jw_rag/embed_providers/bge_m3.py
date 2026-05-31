"""BGE-M3 dense embed provider.

Lazy-loads `sentence-transformers`. Auto-detects target:
  - mlx if Apple Silicon + mlx installed (runs ST with device='mps')
  - nvidia if torch.cuda.is_available()
  - cpu otherwise
"""

from __future__ import annotations

import importlib.util
import logging
import platform
from typing import Any

import numpy as np

from jw_rag.embed import l2_normalize
from jw_rag.embed_providers.factory import Target

logger = logging.getLogger(__name__)

_MODEL_NAME = "BAAI/bge-m3"


def _detect_target() -> Target:
    if platform.processor() == "arm" and importlib.util.find_spec("mlx") is not None:
        return "mlx"
    torch_spec = importlib.util.find_spec("torch")
    if torch_spec is not None:
        try:
            import torch  # type: ignore[import-not-found]

            if torch.cuda.is_available():
                return "nvidia"
        except Exception:  # noqa: BLE001
            pass
    return "cpu"


class BGEM3Provider:
    name = "bge-m3"
    dim = 1024

    def __init__(self) -> None:
        self._target: Target | None = None
        self._model: Any = None

    @property
    def target(self) -> Target:
        if self._target is None:
            self._target = _detect_target()
        return self._target

    def is_available(self) -> bool:
        return importlib.util.find_spec("sentence_transformers") is not None

    def _ensure_model(self) -> Any:
        if self._model is None:
            from sentence_transformers import SentenceTransformer  # type: ignore[import-not-found]

            device = "mps" if self.target == "mlx" else ("cuda" if self.target == "nvidia" else "cpu")
            self._model = SentenceTransformer(_MODEL_NAME, device=device)
        return self._model

    def embed(self, texts: list[str]) -> np.ndarray:
        if not texts:
            return np.zeros((0, self.dim), dtype=np.float32)
        model = self._ensure_model()
        vecs = model.encode(texts, normalize_embeddings=True, convert_to_numpy=True)
        return l2_normalize(vecs.astype(np.float32))
