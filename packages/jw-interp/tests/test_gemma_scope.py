"""Tests for jw_interp.gemma_scope.

The `sae_lens` extra is optional; most tests here exercise the metadata
mapping and the GemmaScopeSAE numpy methods using a hand-rolled inner
object that mimics SAELens's encode/decode signature. The load path is
covered by an importorskip test.
"""

from __future__ import annotations

import numpy as np
import pytest

from jw_interp.gemma_scope import (
    GemmaScopeSAE,
    _resolve_release,
    load_gemma_scope_sae,
)


class _FakeSAELensSAE:
    """Mimics the encode/decode contract of `sae_lens.SAE` for tests."""

    def __init__(self, d_in: int, d_sae: int) -> None:
        torch = pytest.importorskip("torch")
        rng = np.random.default_rng(0)
        self.W_enc = torch.from_numpy(
            rng.standard_normal((d_sae, d_in)).astype(np.float32)
        )
        self.W_dec = torch.from_numpy(
            rng.standard_normal((d_in, d_sae)).astype(np.float32)
        )

        class _Cfg:
            pass

        cfg = _Cfg()
        cfg.d_in = d_in
        cfg.d_sae = d_sae
        self.cfg = cfg

    def encode(self, x):
        # ReLU(xW_enc^T)
        import torch

        return torch.relu(x @ self.W_enc.T)

    def decode(self, z):
        return z @ self.W_dec.T


def test_resolve_release_for_known_combinations() -> None:
    assert _resolve_release("gemma-2-2b", "resid_post") == "gemma-scope-2b-pt-res-canonical"
    assert _resolve_release("gemma-2-2b", "mlp_out") == "gemma-scope-2b-pt-mlp-canonical"
    assert _resolve_release("gemma-2-9b", "attn_out") == "gemma-scope-9b-pt-att-canonical"


def test_resolve_release_rejects_unknown() -> None:
    with pytest.raises(KeyError, match="No Gemma Scope release"):
        _resolve_release("gemma-2-99b", "resid_post")  # type: ignore[arg-type]
    with pytest.raises(KeyError):
        _resolve_release("gemma-2-2b", "bogus_site")  # type: ignore[arg-type]


def test_gemma_scope_sae_encode_decode_round_trip() -> None:
    pytest.importorskip("torch")
    inner = _FakeSAELensSAE(d_in=16, d_sae=32)
    sae = GemmaScopeSAE(
        layer=5,
        site="resid_post",
        d_model=16,
        d_sae=32,
        _inner=inner,
    )
    residual = np.ones((4, 16), dtype=np.float32)
    sparse = sae.encode(residual)
    assert sparse.shape == (4, 32)
    recon = sae.decode(sparse)
    assert recon.shape == (4, 16)


def test_gemma_scope_sae_encode_rejects_wrong_shape() -> None:
    pytest.importorskip("torch")
    sae = GemmaScopeSAE(
        layer=0,
        site="resid_post",
        d_model=16,
        d_sae=32,
        _inner=_FakeSAELensSAE(d_in=16, d_sae=32),
    )
    with pytest.raises(ValueError, match="must be"):
        sae.encode(np.zeros((4, 17), dtype=np.float32))


def test_gemma_scope_sae_reconstruction_error_finite() -> None:
    pytest.importorskip("torch")
    inner = _FakeSAELensSAE(d_in=12, d_sae=24)
    sae = GemmaScopeSAE(
        layer=0,
        site="resid_post",
        d_model=12,
        d_sae=24,
        _inner=inner,
    )
    rng = np.random.default_rng(7)
    residual = rng.standard_normal((6, 12)).astype(np.float32)
    err = sae.reconstruction_error(residual)
    assert np.isfinite(err)
    assert err >= 0.0


def test_load_gemma_scope_sae_without_sae_lens_raises() -> None:
    # We don't have sae_lens installed in CI; verify the error message.
    try:
        import sae_lens  # noqa: F401
    except ImportError:
        with pytest.raises(ImportError, match="sae_lens"):
            load_gemma_scope_sae(
                model_name="gemma-2-2b",
                site="resid_post",
                layer=0,
            )
    else:  # pragma: no cover — only on full installs
        pytest.skip("sae_lens installed; cannot test missing-dep path")


def test_summarize_gemma_features_signature() -> None:
    pytest.importorskip("torch")
    from jw_interp.gemma_scope import summarize_gemma_features

    inner = _FakeSAELensSAE(d_in=8, d_sae=16)
    sae = GemmaScopeSAE(
        layer=0,
        site="resid_post",
        d_model=8,
        d_sae=16,
        _inner=inner,
    )
    rng = np.random.default_rng(11)
    acts = rng.standard_normal((20, 8)).astype(np.float32)
    labels = np.zeros(20, dtype=bool)
    labels[:10] = True
    summaries = summarize_gemma_features(sae, acts, labels, top_n=4)
    assert len(summaries) == 4
