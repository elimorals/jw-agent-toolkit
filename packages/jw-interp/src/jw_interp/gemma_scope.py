"""Gemma Scope SAE adapter (SAELens-backed).

Gemma Scope releases JumpReLU SAEs over Gemma 2 (2B/9B/27B). Unlike
Qwen-Scope, the SAEs are integrated with `sae_lens` — we don't load raw
``.pt`` files ourselves. Instead this module wraps ``sae_lens.SAE`` and
exposes the same numpy interface as :mod:`jw_interp.qwen_scope`, so
downstream code (probing, feature discovery, cross-family agreement) can
treat both adapters interchangeably.

Hook sites available in Gemma Scope (for ``gemma-2-2b`` PT):
  - ``"gemma-scope-2b-pt-res-canonical"`` — residual stream
  - ``"gemma-scope-2b-pt-mlp-canonical"`` — MLP output
  - ``"gemma-scope-2b-pt-att-canonical"`` — attention output

Released widths: 16k (canonical), 32k, 65k, 131k, 262k, 524k.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

import numpy as np

from jw_interp.qwen_scope import (
    FeatureActivationSummary,
    summarize_feature_activations,
)

if TYPE_CHECKING:  # pragma: no cover
    pass

logger = logging.getLogger(__name__)


Site = Literal["resid_post", "mlp_out", "attn_out"]


_RELEASE_MAP = {
    ("gemma-2-2b", "resid_post"): "gemma-scope-2b-pt-res-canonical",
    ("gemma-2-2b", "mlp_out"): "gemma-scope-2b-pt-mlp-canonical",
    ("gemma-2-2b", "attn_out"): "gemma-scope-2b-pt-att-canonical",
    ("gemma-2-9b", "resid_post"): "gemma-scope-9b-pt-res-canonical",
    ("gemma-2-9b", "mlp_out"): "gemma-scope-9b-pt-mlp-canonical",
    ("gemma-2-9b", "attn_out"): "gemma-scope-9b-pt-att-canonical",
}


@dataclass(frozen=True)
class GemmaScopeSAE:
    """JumpReLU SAE from Gemma Scope, wrapped to expose a numpy interface.

    Use :func:`load_gemma_scope_sae` to build one. The underlying
    ``sae_lens.SAE`` object is held in ``_inner`` so we can run forward
    passes via torch when the user opts into the extra; the numpy
    ``encode`` method handles the bridging.
    """

    layer: int
    site: Site
    d_model: int
    d_sae: int
    _inner: object  # sae_lens.SAE — kept as object to avoid hard dep at type-check
    release_id: str = ""
    sae_id: str = ""

    def encode(self, residual: np.ndarray) -> np.ndarray:
        """Encode ``(n, d_model)`` activations via the JumpReLU SAE.

        Numpy in, numpy out. Torch + the wrapped SAE are used internally.
        """
        if residual.ndim != 2 or residual.shape[1] != self.d_model:
            raise ValueError(
                f"residual must be (n, {self.d_model}), got {residual.shape}"
            )
        import torch  # local to keep module importable without torch

        t = torch.from_numpy(residual.astype(np.float32))
        with torch.inference_mode():
            sparse = self._inner.encode(t)  # type: ignore[attr-defined]
        return sparse.detach().to(torch.float32).cpu().numpy()

    def decode(self, sparse_acts: np.ndarray) -> np.ndarray:
        if sparse_acts.ndim != 2 or sparse_acts.shape[1] != self.d_sae:
            raise ValueError(
                f"sparse_acts must be (n, {self.d_sae}), got {sparse_acts.shape}"
            )
        import torch

        t = torch.from_numpy(sparse_acts.astype(np.float32))
        with torch.inference_mode():
            recon = self._inner.decode(t)  # type: ignore[attr-defined]
        return recon.detach().to(torch.float32).cpu().numpy()

    def reconstruction_error(self, residual: np.ndarray) -> float:
        sparse = self.encode(residual)
        recon = self.decode(sparse)
        return float(((residual - recon) ** 2).mean())


def _resolve_release(model_name: str, site: Site) -> str:
    """Map (model, site) → SAELens release id. Raises if unknown."""
    key = (model_name, site)
    if key not in _RELEASE_MAP:
        available = sorted({m for m, _ in _RELEASE_MAP.keys()})
        sites = sorted({s for _, s in _RELEASE_MAP.keys()})
        raise KeyError(
            f"No Gemma Scope release registered for model={model_name!r} "
            f"site={site!r}. Available models: {available}. Sites: {sites}."
        )
    return _RELEASE_MAP[key]


def load_gemma_scope_sae(
    *,
    model_name: str,
    site: Site,
    layer: int,
    width: str = "16k",
    l0: int | None = None,
    device: str = "cpu",
) -> GemmaScopeSAE:
    """Load one Gemma Scope SAE via SAELens.

    Args:
      model_name: e.g. ``"gemma-2-2b"`` (PT/base).
      site: ``"resid_post"`` | ``"mlp_out"`` | ``"attn_out"``.
      layer: layer index.
      width: SAE width tag — ``"16k"`` (default) or ``"32k"``, ``"65k"``, ...
      l0: optional L0 sparsity selector. When ``None`` we ask SAELens for the
        canonical variant.
      device: ``"cpu"`` | ``"cuda"`` | ``"mps"``.

    Returns:
      A ``GemmaScopeSAE`` wrapping the SAELens object.
    """
    try:
        from sae_lens import SAE  # type: ignore[import-not-found]
    except ImportError as exc:  # pragma: no cover
        raise ImportError(
            "Gemma Scope loading requires `sae_lens`. Install with: "
            "uv sync --extra sae"
        ) from exc

    release = _resolve_release(model_name, site)
    # SAELens id pattern for canonical Gemma Scope:
    #   "layer_{N}/width_{W}/canonical" or with explicit L0
    if l0 is None:
        sae_id = f"layer_{layer}/width_{width}/canonical"
    else:
        sae_id = f"layer_{layer}/width_{width}/average_l0_{l0}"

    sae_obj, _cfg, _stats = SAE.from_pretrained(
        release=release, sae_id=sae_id, device=device
    )
    d_model = int(getattr(sae_obj.cfg, "d_in"))
    d_sae = int(getattr(sae_obj.cfg, "d_sae"))
    return GemmaScopeSAE(
        layer=layer,
        site=site,
        d_model=d_model,
        d_sae=d_sae,
        _inner=sae_obj,
        release_id=release,
        sae_id=sae_id,
    )


# Re-export feature discovery helper. The signature accepts any object with
# ``encode(residual)`` returning a (n, d_sae) numpy array — both
# QwenScopeSAE and GemmaScopeSAE satisfy this.
def summarize_gemma_features(
    sae: GemmaScopeSAE,
    activations: np.ndarray,
    labels: np.ndarray,
    *,
    top_n: int = 32,
) -> list[FeatureActivationSummary]:
    """Wrapper that runs the QwenScope feature summarizer on a Gemma SAE.

    The two formats are functionally compatible at the numpy level.
    """
    return summarize_feature_activations(sae, activations, labels, top_n=top_n)  # type: ignore[arg-type]
