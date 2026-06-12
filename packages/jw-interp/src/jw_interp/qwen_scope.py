"""Qwen-Scope SAE adapter.

Loads ``SAE-Res-Qwen3.5-<size>-W<width>-L0_<k>`` checkpoints (one ``.pt`` per
layer) and applies the TopK SAE forward to residual activations.

Checkpoint format (from the HF model card)::

    sae = torch.load(f"layer{N}.sae.pt", map_location="cpu")
    W_enc: (d_sae, d_model)
    b_enc: (d_sae,)
    W_dec: (d_model, d_sae)
    b_dec: (d_model,)

Encoder forward (TopK)::

    pre = residual @ W_enc.T + b_enc        # (n, d_sae)
    topk_vals, topk_idx = pre.topk(k, dim=-1)
    acts = zeros_like(pre)
    acts.scatter_(-1, topk_idx, topk_vals)
    # decode: residual_hat = acts @ W_dec.T + b_dec

This module avoids a hard torch dep at import time: the SAE struct itself
holds numpy arrays and we use numpy for encoding. A torch fast path can be
added later if needed. Loading from ``.pt`` files requires ``torch`` only
to deserialize the pickle.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

import numpy as np

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class QwenScopeSAE:
    """One Qwen-Scope SAE at one layer (TopK over residual stream).

    Arrays are numpy float32.
    ``k`` is the TopK sparsity (defaults to 50 per the public Qwen-Scope
    release, but it is decodable from the filename or model card).
    """

    layer: int
    W_enc: np.ndarray  # (d_sae, d_model)
    b_enc: np.ndarray  # (d_sae,)
    W_dec: np.ndarray  # (d_model, d_sae)
    b_dec: np.ndarray  # (d_model,)
    k: int

    @property
    def d_model(self) -> int:
        return int(self.W_enc.shape[1])

    @property
    def d_sae(self) -> int:
        return int(self.W_enc.shape[0])

    def encode(self, residual: np.ndarray) -> np.ndarray:
        """TopK encode. Input ``(n, d_model)`` → output ``(n, d_sae)`` sparse.

        Each row keeps the top-``k`` activations and zeros the rest. Returns
        a dense ``ndarray`` with at most ``k`` non-zero entries per row.
        """
        if residual.ndim != 2 or residual.shape[1] != self.d_model:
            raise ValueError(
                f"residual must be (n, {self.d_model}), got shape {residual.shape}"
            )
        pre = residual @ self.W_enc.T + self.b_enc  # (n, d_sae)
        # TopK along axis=1
        n, d_sae = pre.shape
        if self.k >= d_sae:
            return pre.copy()
        # Use np.argpartition for O(n·d_sae) selection
        idx = np.argpartition(-pre, kth=self.k - 1, axis=1)[:, : self.k]
        out = np.zeros_like(pre)
        rows = np.arange(n)[:, None]
        out[rows, idx] = pre[rows, idx]
        return out

    def decode(self, sparse_acts: np.ndarray) -> np.ndarray:
        """Reconstruct ``(n, d_model)`` from sparse SAE activations."""
        if sparse_acts.ndim != 2 or sparse_acts.shape[1] != self.d_sae:
            raise ValueError(
                f"sparse_acts must be (n, {self.d_sae}), got shape {sparse_acts.shape}"
            )
        return sparse_acts @ self.W_dec.T + self.b_dec

    def reconstruction_error(self, residual: np.ndarray) -> float:
        """Mean squared reconstruction error over rows."""
        sparse = self.encode(residual)
        recon = self.decode(sparse)
        return float(((residual - recon) ** 2).mean())


def load_qwen_scope_sae(
    checkpoint_path: str | Path,
    *,
    layer: int,
    k: int = 50,
) -> QwenScopeSAE:
    """Load one ``layer{N}.sae.pt`` checkpoint into a ``QwenScopeSAE``.

    Requires torch only for the unpickling step; arrays are immediately
    moved to numpy. The torch import is deferred so importing this module
    without torch installed does not crash.
    """
    path = Path(checkpoint_path)
    if not path.exists():
        raise FileNotFoundError(f"Qwen-Scope checkpoint not found: {path}")

    try:
        import torch
    except ImportError as exc:  # pragma: no cover
        raise ImportError(
            "Loading Qwen-Scope checkpoints requires torch to deserialize "
            "the .pt files. Install with: uv sync --extra torch"
        ) from exc

    # weights_only=True prevents arbitrary pickle execution. Qwen-Scope
    # checkpoints are dict[str, Tensor] so the strict loader is sufficient.
    payload: dict[str, torch.Tensor] = torch.load(
        str(path), map_location="cpu", weights_only=True
    )
    required = ("W_enc", "b_enc", "W_dec", "b_dec")
    missing = [k for k in required if k not in payload]
    if missing:
        raise ValueError(
            f"Qwen-Scope checkpoint at {path} missing keys: {missing}. "
            f"Found: {sorted(payload.keys())}"
        )

    return QwenScopeSAE(
        layer=layer,
        W_enc=payload["W_enc"].to(torch.float32).numpy(),
        b_enc=payload["b_enc"].to(torch.float32).numpy(),
        W_dec=payload["W_dec"].to(torch.float32).numpy(),
        b_dec=payload["b_dec"].to(torch.float32).numpy(),
        k=k,
    )


# ---------------------------------------------------------------------------
# Feature discovery: which SAE features fire most on a principle's positive
# prompts? Used in F80.3 to map principles → SAE feature indices.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class FeatureActivationSummary:
    """How often / how strongly each feature fired on a labeled batch."""

    layer: int
    feature_idx: int
    activation_rate_positive: float
    activation_rate_negative: float
    mean_activation_positive: float
    mean_activation_negative: float

    @property
    def differential_rate(self) -> float:
        """Positive activation rate minus negative — high = principle-specific."""
        return self.activation_rate_positive - self.activation_rate_negative


def summarize_feature_activations(
    sae: QwenScopeSAE,
    activations: np.ndarray,
    labels: np.ndarray,
    *,
    top_n: int = 32,
) -> list[FeatureActivationSummary]:
    """Identify SAE features whose activation correlates with the principle label.

    Returns the top ``top_n`` features by ``|activation_rate_pos - rate_neg|``.
    Useful for mapping a principle to candidate features for auto-interp.
    """
    if activations.shape[0] != labels.shape[0]:
        raise ValueError(
            f"shape mismatch activations={activations.shape} labels={labels.shape}"
        )
    sparse = sae.encode(activations)  # (n, d_sae)
    # Binary activation mask
    active = sparse > 0  # (n, d_sae)
    pos_mask = labels
    neg_mask = ~labels
    n_pos = max(int(pos_mask.sum()), 1)
    n_neg = max(int(neg_mask.sum()), 1)

    rate_pos = active[pos_mask].sum(axis=0) / n_pos  # (d_sae,)
    rate_neg = active[neg_mask].sum(axis=0) / n_neg
    diff = np.abs(rate_pos - rate_neg)
    top_idx = np.argpartition(-diff, kth=min(top_n - 1, len(diff) - 1))[:top_n]
    top_idx = top_idx[np.argsort(-diff[top_idx])]

    # Mean activation magnitude per side
    sum_pos = (sparse * pos_mask[:, None]).sum(axis=0)
    sum_neg = (sparse * neg_mask[:, None]).sum(axis=0)
    mean_pos = sum_pos / n_pos
    mean_neg = sum_neg / n_neg

    out: list[FeatureActivationSummary] = []
    for fi in top_idx:
        out.append(
            FeatureActivationSummary(
                layer=sae.layer,
                feature_idx=int(fi),
                activation_rate_positive=float(rate_pos[fi]),
                activation_rate_negative=float(rate_neg[fi]),
                mean_activation_positive=float(mean_pos[fi]),
                mean_activation_negative=float(mean_neg[fi]),
            )
        )
    return out
