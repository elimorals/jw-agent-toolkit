"""Steering vectors derived from contrastive activation batches.

A steering vector for a principle at a layer is::

    v = mean(activations | positive) - mean(activations | negative)

Adding ``α · v`` to the residual stream at that layer **pushes** the model
toward the positive class; subtracting **pulls** it away. F80.2 uses this to
validate causal effects:

  - If ``+α·v`` makes the model more faithful to the principle AND
    ``-α·v`` makes it less faithful → the direction is *causal*.
  - If neither direction changes the conduct → the probe was capturing
    correlation, not causation. Shortcut detected.

This module provides:
  - ``SteeringVector`` dataclass (one per principle × layer).
  - ``compute_steering_vector(batch)``.
  - ``compute_steering_vectors_for_principle(batches)``.
  - ``apply_steering_to_residual(residual, vector, alpha)`` — pure numpy.
  - ``project_out(activations, vector)`` — null out a direction (ablation).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

import numpy as np

from jw_interp.models import ActivationBatch


@dataclass(frozen=True)
class SteeringVector:
    """A direction in residual space encoding presence of a principle.

    ``vector`` is unit-norm; ``magnitude`` is the original signal strength
    (``‖μ_pos − μ_neg‖``) — useful to choose a reasonable ``alpha`` at
    application time.
    """

    principle_id: str
    layer: int
    hook_name: str
    vector: np.ndarray
    magnitude: float
    n_positive: int
    n_negative: int

    @property
    def hidden_size(self) -> int:
        return int(self.vector.shape[0])


def compute_steering_vector(
    batch: ActivationBatch,
    principle_id: str,
    *,
    normalize: bool = True,
) -> SteeringVector:
    """Difference-of-means steering vector for one batch."""
    pos = batch.activations[batch.labels]
    neg = batch.activations[~batch.labels]
    if pos.shape[0] == 0 or neg.shape[0] == 0:
        raise ValueError(
            f"steering vector requires at least one of each label; got "
            f"pos={pos.shape[0]} neg={neg.shape[0]}"
        )
    diff = pos.mean(axis=0) - neg.mean(axis=0)
    magnitude = float(np.linalg.norm(diff))
    if normalize and magnitude > 0:
        unit = diff / magnitude
    else:
        unit = diff
    return SteeringVector(
        principle_id=principle_id,
        layer=batch.layer,
        hook_name=batch.hook_name,
        vector=unit.astype(np.float32),
        magnitude=magnitude,
        n_positive=int(pos.shape[0]),
        n_negative=int(neg.shape[0]),
    )


def compute_steering_vectors_for_principle(
    batches: Sequence[ActivationBatch],
    principle_id: str,
    *,
    normalize: bool = True,
) -> list[SteeringVector]:
    """One steering vector per layer for a given principle."""
    return [compute_steering_vector(b, principle_id, normalize=normalize) for b in batches]


def apply_steering_to_residual(
    residual: np.ndarray,
    vector: SteeringVector,
    *,
    alpha: float = 1.0,
) -> np.ndarray:
    """Add ``alpha · vector`` to a residual stream activation.

    ``residual`` can be ``(hidden_size,)`` or ``(batch, hidden_size)`` —
    broadcasting handles both. Returns a new array; input is not mutated.
    """
    if residual.shape[-1] != vector.hidden_size:
        raise ValueError(
            f"residual hidden_size {residual.shape[-1]} != "
            f"steering vector hidden_size {vector.hidden_size}"
        )
    return residual + alpha * vector.vector


def project_out(
    activations: np.ndarray,
    vector: SteeringVector,
) -> np.ndarray:
    """Remove the component of ``activations`` along ``vector``.

    Useful for ablation experiments: "what happens if this principle's
    feature is *not* available in the residual?".
    Assumes ``vector.vector`` is unit-norm (the default of
    ``compute_steering_vector``).
    """
    if activations.shape[-1] != vector.hidden_size:
        raise ValueError(
            f"activations hidden_size {activations.shape[-1]} != "
            f"steering vector hidden_size {vector.hidden_size}"
        )
    v = vector.vector
    # Project each row onto v, then subtract that projection.
    projections = activations @ v  # shape (batch,) or scalar
    return activations - np.outer(projections, v) if activations.ndim == 2 else activations - projections * v


# ---------------------------------------------------------------------------
# Effect-size summary (for reporting)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SteeringEffect:
    """Result of steering at a (principle, layer, alpha) configuration.

    The fields ``probe_score_positive`` and ``probe_score_negative`` are the
    probe's confidence that the activation belongs to the positive class
    *after* steering. The expected directional effects:

      - ``+alpha``: positive prompts → higher probe score (stays/improves)
        but more importantly, *negative* prompts also get pushed up.
      - ``-alpha``: positive prompts → lower probe score; negative prompts
        get pushed down further. A causal direction should show monotone
        behavior under monotone alpha sweeps.
    """

    principle_id: str
    layer: int
    alpha: float
    probe_score_positive: float
    probe_score_negative: float
    direction: Literal["positive", "negative"]


def evaluate_steering_effect(
    batch: ActivationBatch,
    vector: SteeringVector,
    probe_predict_proba,
    *,
    alpha: float = 1.0,
) -> SteeringEffect:
    """Apply steering to a batch, then run the probe on the steered activations.

    ``probe_predict_proba`` is a callable that takes ``(n, hidden)`` and
    returns ``(n,)`` positive-class probabilities. Typically the bound method
    ``LinearProbe.predict_proba``.
    """
    steered = apply_steering_to_residual(batch.activations, vector, alpha=alpha)
    proba = probe_predict_proba(steered)
    return SteeringEffect(
        principle_id=vector.principle_id,
        layer=batch.layer,
        alpha=alpha,
        probe_score_positive=float(proba[batch.labels].mean()),
        probe_score_negative=float(proba[~batch.labels].mean()),
        direction="positive" if alpha >= 0 else "negative",
    )
