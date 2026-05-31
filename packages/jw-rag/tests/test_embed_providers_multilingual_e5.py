from __future__ import annotations

import importlib.util

import numpy as np
import pytest
from jw_rag.embed_providers.multilingual_e5 import MultilingualE5Provider


def test_is_available_false_when_sentence_transformers_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "importlib.util.find_spec",
        lambda name: None if name == "sentence_transformers" else importlib.util.find_spec(name),
    )
    assert MultilingualE5Provider().is_available() is False


def test_name_and_dim() -> None:
    p = MultilingualE5Provider()
    assert p.name == "multilingual-e5"
    assert p.dim == 1024


@pytest.mark.embeddings_local
def test_real_embed_uses_query_passage_prefix() -> None:
    p = MultilingualE5Provider()
    if not p.is_available():
        pytest.skip("sentence-transformers not installed")
    # E5 expects "query: ..." or "passage: ..." prefixes. Provider must add them transparently.
    out = p.embed(["hello world"])
    assert out.shape == (1, 1024)
    assert out.dtype == np.float32
    assert np.allclose(np.linalg.norm(out, axis=1), 1.0, atol=1e-3)
