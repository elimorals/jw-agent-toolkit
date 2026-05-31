from __future__ import annotations

import importlib.util
import sys
import types

import numpy as np
import pytest
from jw_rag.embed_providers.voyage import VoyageMultilingualProvider


def test_is_available_false_without_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("VOYAGE_API_KEY", raising=False)
    assert VoyageMultilingualProvider().is_available() is False


def test_is_available_false_without_sdk(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VOYAGE_API_KEY", "x")
    monkeypatch.setattr(
        "importlib.util.find_spec",
        lambda name: None if name == "voyageai" else importlib.util.find_spec(name),
    )
    assert VoyageMultilingualProvider().is_available() is False


def test_embed_uses_stub_sdk(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VOYAGE_API_KEY", "fake")

    class StubResp:
        embeddings = [[1.0, 0.0] + [0.0] * 1022, [0.0, 2.0] + [0.0] * 1022]

    class StubClient:
        def __init__(self, api_key: str) -> None:
            self.api_key = api_key

        def embed(self, texts: list[str], model: str, input_type: str) -> StubResp:
            return StubResp()

    fake_module = types.ModuleType("voyageai")
    fake_module.Client = StubClient  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "voyageai", fake_module)

    out = VoyageMultilingualProvider().embed(["a", "b"])
    assert out.shape == (2, 1024)
    assert np.allclose(np.linalg.norm(out, axis=1), 1.0, atol=1e-5)
