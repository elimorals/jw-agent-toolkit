"""Tests for FakeColPaliEmbedder and FakeRasterizer.

Determinism is the whole point: same input bytes → same vectors. That lets
tests assert exact MaxSim scores without ever touching a real GPU model.
"""

from __future__ import annotations

import hashlib
import io

import numpy as np
from jw_rag.visual.fakes import FakeColPaliEmbedder, FakeRasterizer
from PIL import Image


def _img_bytes(image: Image.Image) -> bytes:
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    return buf.getvalue()


def test_fake_embedder_shape_and_dtype() -> None:
    e = FakeColPaliEmbedder(dim=128, n_patches=64)
    img = Image.new("RGB", (256, 256), color=(255, 0, 0))
    vecs = e.embed_image(img)
    assert vecs.shape == (64, 128)
    assert vecs.dtype == np.float16


def test_fake_embedder_is_deterministic() -> None:
    e = FakeColPaliEmbedder(dim=128, n_patches=32)
    img = Image.new("RGB", (128, 128), color=(0, 255, 0))
    a = e.embed_image(img)
    b = e.embed_image(img)
    np.testing.assert_array_equal(a, b)


def test_fake_embedder_different_images_differ() -> None:
    e = FakeColPaliEmbedder(dim=128, n_patches=32)
    a = e.embed_image(Image.new("RGB", (128, 128), color=(0, 255, 0)))
    b = e.embed_image(Image.new("RGB", (128, 128), color=(0, 0, 255)))
    # Different bytes → different seed → different vectors.
    assert not np.array_equal(a, b)


def test_fake_embedder_query_uses_text_seed() -> None:
    e = FakeColPaliEmbedder(dim=128, n_patches=32)
    q1 = e.embed_query("hello")
    q2 = e.embed_query("hello")
    q3 = e.embed_query("world")
    np.testing.assert_array_equal(q1, q2)
    assert not np.array_equal(q1, q3)
    assert q1.shape[1] == 128
    assert q1.shape[0] >= 1  # at least one query token


def test_fake_embedder_is_available_always_true() -> None:
    assert FakeColPaliEmbedder.is_available() is True


def test_fake_rasterizer_yields_blank_pages() -> None:
    r = FakeRasterizer(n_pages=3, size=(64, 64))
    pages = list(r.rasterize_pdf(b"any-bytes"))
    assert len(pages) == 3
    for _idx, img in pages:
        assert isinstance(img, Image.Image)
        assert img.size == (64, 64)
    assert [idx for idx, _ in pages] == [0, 1, 2]


def test_fake_rasterizer_varies_per_page() -> None:
    """Each page gets a different fill so embeddings will differ."""
    r = FakeRasterizer(n_pages=3, size=(64, 64))
    pages = list(r.rasterize_pdf(b"src"))
    digests = {hashlib.sha256(_img_bytes(img)).hexdigest() for _, img in pages}
    assert len(digests) == 3
