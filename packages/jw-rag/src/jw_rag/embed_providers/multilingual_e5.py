"""intfloat/multilingual-e5-large dense embed provider.

E5 requires a 'query: ' or 'passage: ' prefix per text. Since the provider
contract is text-in-text-out and the caller doesn't know whether a string
is a query or a passage, we default to 'passage:' (corpus side), and the
calling layer can re-embed queries explicitly when needed.

For jw-rag's VectorStore use case, both indexing and querying paths route
through the same Embedder, so this is consistent across both sides.
"""

from __future__ import annotations

import importlib.util
from typing import Any

import numpy as np

from jw_rag.embed import l2_normalize
from jw_rag.embed_providers.bge_m3 import _detect_target
from jw_rag.embed_providers.factory import Target

_MODEL_NAME = "intfloat/multilingual-e5-large"


class MultilingualE5Provider:
    name = "multilingual-e5"
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
        prefixed = [f"passage: {t}" for t in texts]
        model = self._ensure_model()
        vecs = model.encode(prefixed, normalize_embeddings=True, convert_to_numpy=True)
        return l2_normalize(vecs.astype(np.float32))
