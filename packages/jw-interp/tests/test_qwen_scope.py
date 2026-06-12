"""Tests for jw_interp.qwen_scope.

We don't require torch for most tests — `QwenScopeSAE` works on numpy
arrays directly. We only need torch for the `load_qwen_scope_sae` round-trip
test (importorskip).
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from jw_interp.qwen_scope import (
    QwenScopeSAE,
    summarize_feature_activations,
)


def _make_sae(d_model: int = 16, d_sae: int = 64, k: int = 8) -> QwenScopeSAE:
    rng = np.random.default_rng(0)
    W_enc = rng.standard_normal((d_sae, d_model)).astype(np.float32)
    b_enc = rng.standard_normal(d_sae).astype(np.float32) * 0.01
    W_dec = rng.standard_normal((d_model, d_sae)).astype(np.float32)
    b_dec = rng.standard_normal(d_model).astype(np.float32) * 0.01
    return QwenScopeSAE(
        layer=0,
        W_enc=W_enc,
        b_enc=b_enc,
        W_dec=W_dec,
        b_dec=b_dec,
        k=k,
    )


def test_qwen_sae_dimensions() -> None:
    sae = _make_sae(d_model=32, d_sae=128, k=10)
    assert sae.d_model == 32
    assert sae.d_sae == 128
    assert sae.k == 10


def test_qwen_sae_encode_shapes() -> None:
    sae = _make_sae()
    rng = np.random.default_rng(1)
    residual = rng.standard_normal((5, sae.d_model)).astype(np.float32)
    sparse = sae.encode(residual)
    assert sparse.shape == (5, sae.d_sae)


def test_qwen_sae_encode_enforces_topk_sparsity() -> None:
    sae = _make_sae(d_model=16, d_sae=64, k=5)
    rng = np.random.default_rng(2)
    residual = rng.standard_normal((4, 16)).astype(np.float32)
    sparse = sae.encode(residual)
    non_zero_per_row = (sparse != 0).sum(axis=1)
    # Allow exactly k non-zeros (TopK may include zero if pre-acts are 0)
    assert (non_zero_per_row <= sae.k).all()
    # In practice with random data, exactly k per row
    assert non_zero_per_row.max() == sae.k


def test_qwen_sae_encode_rejects_wrong_dim() -> None:
    sae = _make_sae(d_model=16)
    bad = np.zeros((3, 17), dtype=np.float32)
    with pytest.raises(ValueError, match="must be"):
        sae.encode(bad)


def test_qwen_sae_decode_shapes() -> None:
    sae = _make_sae()
    rng = np.random.default_rng(3)
    sparse = rng.standard_normal((4, sae.d_sae)).astype(np.float32)
    recon = sae.decode(sparse)
    assert recon.shape == (4, sae.d_model)


def test_qwen_sae_reconstruction_error_finite() -> None:
    sae = _make_sae()
    rng = np.random.default_rng(4)
    residual = rng.standard_normal((8, sae.d_model)).astype(np.float32)
    err = sae.reconstruction_error(residual)
    assert np.isfinite(err)
    assert err >= 0.0


def test_qwen_sae_topk_keeps_largest_values() -> None:
    """The k features kept should be the ones with the largest pre-activations."""
    sae = _make_sae(d_model=8, d_sae=16, k=3)
    # Construct a residual so we can predict pre-activations
    residual = np.array([[1.0] * 8], dtype=np.float32)
    pre = residual @ sae.W_enc.T + sae.b_enc
    top_indices = np.argsort(-pre[0])[: sae.k]
    sparse = sae.encode(residual)
    non_zero = np.where(sparse[0] != 0)[0]
    assert set(non_zero.tolist()) == set(top_indices.tolist())


def test_summarize_feature_activations_returns_principled_top_n() -> None:
    """A feature only firing on positives should rank high in differential."""
    d_model = 16
    d_sae = 32
    sae = _make_sae(d_model=d_model, d_sae=d_sae, k=4)

    rng = np.random.default_rng(5)
    n = 40
    activations = rng.standard_normal((n, d_model)).astype(np.float32)
    labels = np.zeros(n, dtype=bool)
    labels[:20] = True

    summaries = summarize_feature_activations(sae, activations, labels, top_n=8)
    assert len(summaries) == 8
    # All entries have valid layer ref
    assert all(s.layer == 0 for s in summaries)
    # Sorted by descending |differential|
    diffs = [abs(s.differential_rate) for s in summaries]
    assert diffs == sorted(diffs, reverse=True)


def test_summarize_rejects_shape_mismatch() -> None:
    sae = _make_sae()
    acts = np.zeros((10, sae.d_model), dtype=np.float32)
    labels = np.zeros(8, dtype=bool)
    with pytest.raises(ValueError, match="shape mismatch"):
        summarize_feature_activations(sae, acts, labels)


# ---------------------------------------------------------------------------
# Loader round-trip (requires torch)
# ---------------------------------------------------------------------------


def test_load_qwen_scope_sae_round_trip(tmp_path: Path) -> None:
    torch = pytest.importorskip("torch")
    from jw_interp.qwen_scope import load_qwen_scope_sae

    payload = {
        "W_enc": torch.randn(64, 16),
        "b_enc": torch.randn(64) * 0.01,
        "W_dec": torch.randn(16, 64),
        "b_dec": torch.randn(16) * 0.01,
    }
    path = tmp_path / "layer3.sae.pt"
    torch.save(payload, str(path))

    sae = load_qwen_scope_sae(path, layer=3, k=10)
    assert sae.layer == 3
    assert sae.d_model == 16
    assert sae.d_sae == 64
    assert sae.k == 10
    # Shapes round-trip correctly
    np.testing.assert_allclose(sae.W_enc, payload["W_enc"].numpy(), atol=1e-6)


def test_load_qwen_scope_sae_rejects_missing_keys(tmp_path: Path) -> None:
    torch = pytest.importorskip("torch")
    from jw_interp.qwen_scope import load_qwen_scope_sae

    incomplete = {"W_enc": torch.randn(4, 4)}
    path = tmp_path / "broken.sae.pt"
    torch.save(incomplete, str(path))
    with pytest.raises(ValueError, match="missing keys"):
        load_qwen_scope_sae(path, layer=0, k=4)


def test_load_qwen_scope_sae_missing_file() -> None:
    from jw_interp.qwen_scope import load_qwen_scope_sae

    with pytest.raises(FileNotFoundError):
        load_qwen_scope_sae("/nonexistent.pt", layer=0)
