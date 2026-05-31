"""Tests for the real ColPali/ColQwen2 providers and factory.

We never actually load the model in CI — only verify:
  - `is_available()` returns False when torch/MLX missing
  - factory raises ConfigError with the actionable hint when no provider
    is available
  - factory returns the FakeColPaliEmbedder when explicitly requested via
    the `prefer_fake=True` argument (test harness escape hatch)
"""

from __future__ import annotations

import pytest

from jw_rag.visual.colpali import (
    ColPaliEmbedder,
    ColQwen2Embedder,
    get_default_visual_embedder,
)
from jw_rag.visual.errors import ConfigError
from jw_rag.visual.fakes import FakeColPaliEmbedder


def test_colpali_is_available_handles_missing_torch(monkeypatch: pytest.MonkeyPatch) -> None:
    """If torch is not importable, is_available(target='nvidia') is False."""
    import jw_rag.visual.colpali as mod

    monkeypatch.setattr(mod, "_torch_cuda_available", lambda: False)
    monkeypatch.setattr(mod, "_mlx_metal_available", lambda: False)
    assert ColPaliEmbedder.is_available(target="nvidia") is False
    assert ColPaliEmbedder.is_available(target="mlx") is False


def test_colqwen2_is_available_handles_missing_backends(monkeypatch: pytest.MonkeyPatch) -> None:
    import jw_rag.visual.colpali as mod

    monkeypatch.setattr(mod, "_torch_cuda_available", lambda: False)
    monkeypatch.setattr(mod, "_mlx_metal_available", lambda: False)
    assert ColQwen2Embedder.is_available(target="nvidia") is False
    assert ColQwen2Embedder.is_available(target="mlx") is False


def test_factory_raises_config_error_when_no_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    import jw_rag.visual.colpali as mod

    monkeypatch.setattr(mod, "_torch_cuda_available", lambda: False)
    monkeypatch.setattr(mod, "_mlx_metal_available", lambda: False)
    with pytest.raises(ConfigError) as exc:
        get_default_visual_embedder()
    msg = str(exc.value)
    assert "uv sync --extra visual" in msg
    assert "FakeColPaliEmbedder" in msg
    assert "JW_VISUAL_ENABLED" in msg


def test_factory_returns_fake_when_prefer_fake() -> None:
    embedder = get_default_visual_embedder(prefer_fake=True)
    assert isinstance(embedder, FakeColPaliEmbedder)


def test_factory_picks_nvidia_first_when_available(monkeypatch: pytest.MonkeyPatch) -> None:
    """If both backends are present, NVIDIA wins (spec rationale)."""
    import jw_rag.visual.colpali as mod

    monkeypatch.setattr(mod, "_torch_cuda_available", lambda: True)
    monkeypatch.setattr(mod, "_mlx_metal_available", lambda: True)

    class _Stub(mod.ColQwen2Embedder):
        def __init__(self, target: str = "nvidia") -> None:
            self.target = target
            self.name = "colqwen2-stub"
            self.dim = 128
            self.max_patches = 1030

    monkeypatch.setattr(mod, "ColQwen2Embedder", _Stub)
    embedder = get_default_visual_embedder()
    assert embedder.target == "nvidia"
