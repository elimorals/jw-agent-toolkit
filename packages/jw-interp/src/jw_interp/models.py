"""Dataclasses for jw-interp.

Kept lean: numpy arrays are stored as-is (no copy), labels as bool numpy arrays,
identifiers as strings. No torch types here so the package is importable without
the `torch` extra.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

import numpy as np


@dataclass(frozen=True)
class ContrastivePair:
    """One contrastive item: a prompt expected to invoke a principle vs a neutral one.

    ``principle_id`` is the YAML id from `jw_eval.principles` (e.g. "PF001-canon-only").
    ``positive`` is the prompt where the principle is expected to be relevant.
    ``negative`` is a matched neutral prompt (same surface form, distinct semantics).
    """

    principle_id: str
    positive: str
    negative: str
    language: str = "es"
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass
class ActivationBatch:
    """A batch of activations captured for a contrastive set, at one layer.

    Shape conventions:
      - ``activations`` is ``(n_samples, hidden_size)`` — pooled per prompt
        (e.g. last-token activation of the residual stream).
      - ``labels`` is ``(n_samples,)`` bool: True = positive (principle invoked).
      - ``prompt_ids`` is ``(n_samples,)`` str: ties each row back to a prompt
        for error analysis.
    """

    layer: int
    hook_name: str  # "resid_post" | "mlp_out" | "attn_out" | ...
    activations: np.ndarray
    labels: np.ndarray
    prompt_ids: list[str]

    def __post_init__(self) -> None:
        if self.activations.ndim != 2:
            raise ValueError(
                f"activations must be 2D (n, d), got shape {self.activations.shape}"
            )
        if self.labels.shape[0] != self.activations.shape[0]:
            raise ValueError(
                f"labels length {self.labels.shape[0]} != activations rows "
                f"{self.activations.shape[0]}"
            )
        if len(self.prompt_ids) != self.activations.shape[0]:
            raise ValueError(
                f"prompt_ids length {len(self.prompt_ids)} != activations rows "
                f"{self.activations.shape[0]}"
            )


@dataclass(frozen=True)
class ProbeResult:
    """Outcome of training one probe at one layer for one principle.

    ``accuracy`` and ``auc`` are on the held-out test split (default 20%).
    ``layer`` is the source layer index, ``hook_name`` is the source hook.
    ``n_train`` / ``n_test`` are sample counts for traceability.
    ``coef`` is the learned probe weight vector (hidden_size,) — kept so
    downstream phases (F80.2 steering) can reuse it.
    """

    principle_id: str
    layer: int
    hook_name: str
    accuracy: float
    auc: float
    n_train: int
    n_test: int
    coef: np.ndarray
    bias: float
    convergence: Literal["converged", "not-converged"] = "converged"


@dataclass
class ProbingDataset:
    """A set of ``ContrastivePair`` for one principle, ready for activation capture.

    Holds the raw text prompts and their flat label vector (the order is
    [positive_0, negative_0, positive_1, negative_1, ...] so capture order is
    deterministic).
    """

    principle_id: str
    pairs: list[ContrastivePair]

    @property
    def n_pairs(self) -> int:
        return len(self.pairs)

    @property
    def n_prompts(self) -> int:
        return 2 * len(self.pairs)

    def flat_prompts(self) -> list[tuple[str, bool, str]]:
        """Return [(prompt_text, is_positive, prompt_id), ...] in capture order."""
        out: list[tuple[str, bool, str]] = []
        for i, p in enumerate(self.pairs):
            out.append((p.positive, True, f"{p.principle_id}::pair{i}::pos"))
            out.append((p.negative, False, f"{p.principle_id}::pair{i}::neg"))
        return out
