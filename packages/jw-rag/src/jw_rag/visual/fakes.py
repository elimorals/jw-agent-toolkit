"""Deterministic fakes for the visual subsystem.

`FakeColPaliEmbedder` seeds a per-image RNG from `sha256(image_bytes)`. Tests
get byte-identical vectors across runs without touching `colpali-engine` or
`torch`. Compatible with the same `embed_image` / `embed_query` shape as the
real provider:

    embed_image(PIL.Image) -> np.ndarray[float16, (n_patches, dim)]
    embed_query(str)       -> np.ndarray[float16, (n_q_tokens, dim)]

`FakeRasterizer` mimics the real `PageRasterizer` interface but never touches
Playwright / pdf2image. It returns blank-but-distinct PIL images keyed by page
index, so downstream embedding stages get distinguishable inputs.
"""

from __future__ import annotations

import hashlib
import io
from collections.abc import Iterator

import numpy as np
from PIL import Image


class FakeColPaliEmbedder:
    """Deterministic stand-in for ColQwen2/ColPali."""

    name = "fake-colpali"
    dim = 128
    max_patches = 1030

    def __init__(self, *, dim: int = 128, n_patches: int = 64) -> None:
        self.dim = dim
        self._n_patches = n_patches
        self.max_patches = n_patches  # store padding uses this

    @classmethod
    def is_available(cls, target: str = "fake") -> bool:  # noqa: ARG003
        return True

    def embed_image(self, image: Image.Image) -> np.ndarray:
        seed = self._seed_from_image(image)
        rng = np.random.default_rng(seed)
        vecs = rng.standard_normal(size=(self._n_patches, self.dim)).astype(np.float16)
        return _l2_normalize_rows(vecs)

    def embed_query(self, query: str) -> np.ndarray:
        # Query length tracks word count so tests can probe sensitivity.
        n_tokens = max(1, len(query.split()))
        seed = int.from_bytes(hashlib.sha256(query.encode("utf-8")).digest()[:8], "big")
        rng = np.random.default_rng(seed)
        vecs = rng.standard_normal(size=(n_tokens, self.dim)).astype(np.float16)
        return _l2_normalize_rows(vecs)

    @staticmethod
    def _seed_from_image(image: Image.Image) -> int:
        buf = io.BytesIO()
        image.save(buf, format="PNG")
        return int.from_bytes(hashlib.sha256(buf.getvalue()).digest()[:8], "big")


def _l2_normalize_rows(arr: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(arr.astype(np.float32), axis=1, keepdims=True)
    norms = np.where(norms == 0, 1.0, norms)
    return (arr.astype(np.float32) / norms).astype(np.float16)


class FakeRasterizer:
    """Returns blank-but-distinct PIL images for tests.

    The fill color encodes the page index so different pages produce different
    `sha256(image_bytes)` and therefore different FakeColPaliEmbedder vectors.
    """

    def __init__(self, *, n_pages: int = 3, size: tuple[int, int] = (768, 1024)) -> None:
        self._n_pages = n_pages
        self._size = size

    def _make_page(self, idx: int) -> Image.Image:
        # Vary RGB per page so embeddings are distinguishable.
        r = (idx * 53) % 256
        g = (idx * 97) % 256
        b = (idx * 151) % 256
        return Image.new("RGB", self._size, color=(r, g, b))

    def rasterize_pdf(self, _data: bytes, *, dpi: int = 200) -> Iterator[tuple[int, Image.Image]]:  # noqa: ARG002
        for i in range(self._n_pages):
            yield i, self._make_page(i)

    def rasterize_epub(self, _path, *, viewport=(768, 1024)) -> Iterator[tuple[int, Image.Image]]:  # noqa: ARG002, ANN001
        for i in range(self._n_pages):
            yield i, self._make_page(i)

    def rasterize_jwpub(self, _path, *, dpi: int = 200) -> Iterator[tuple[int, Image.Image]]:  # noqa: ARG002, ANN001
        for i in range(self._n_pages):
            yield i, self._make_page(i)
