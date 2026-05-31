from __future__ import annotations

import importlib.util
import sys
import types

import numpy as np
import pytest
from jw_rag.embed_providers.cohere import CohereEmbedV3Provider


def test_is_available_false_without_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("COHERE_API_KEY", raising=False)
    assert CohereEmbedV3Provider().is_available() is False


def test_is_available_false_without_sdk(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COHERE_API_KEY", "x")
    monkeypatch.setattr(
        "importlib.util.find_spec",
        lambda name: None if name == "cohere" else importlib.util.find_spec(name),
    )
    assert CohereEmbedV3Provider().is_available() is False


def test_embed_uses_stub_sdk(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COHERE_API_KEY", "fake")
    calls: dict = {}

    class StubResponse:
        embeddings = [[3.0, 4.0] + [0.0] * 1022, [0.0, 0.0, 5.0] + [0.0] * 1021]

    class StubClient:
        def __init__(self, api_key: str) -> None:
            calls["init_key"] = api_key

        def embed(self, *, texts: list[str], model: str, input_type: str) -> StubResponse:
            calls["texts"] = texts
            calls["model"] = model
            calls["input_type"] = input_type
            return StubResponse()

    fake_module = types.ModuleType("cohere")
    fake_module.Client = StubClient  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "cohere", fake_module)

    p = CohereEmbedV3Provider()
    out = p.embed(["hola", "mundo"])
    assert out.shape == (2, 1024)
    assert np.allclose(np.linalg.norm(out, axis=1), 1.0, atol=1e-5)
    assert calls["model"] == "embed-multilingual-v3.0"
    assert calls["input_type"] == "search_document"


def test_safe_repr_truncates_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COHERE_API_KEY", "abcdefgh1234")
    assert "abcdefgh1234" not in repr(CohereEmbedV3Provider())
