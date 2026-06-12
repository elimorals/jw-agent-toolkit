"""Tests for jw_interp.steering."""

from __future__ import annotations

import numpy as np
import pytest

from jw_interp.activations import MockActivationCapturer
from jw_interp.contrastive import ContrastiveSpec, PrincipleContrastiveBuilder
from jw_interp.models import ActivationBatch
from jw_interp.probing import LinearProbe
from jw_interp.steering import (
    SteeringVector,
    apply_steering_to_residual,
    compute_steering_vector,
    compute_steering_vectors_for_principle,
    evaluate_steering_effect,
    project_out,
)


def _separable_batch(n: int = 40, hidden_size: int = 32) -> ActivationBatch:
    spec = ContrastiveSpec(
        principle_id="PF-test",
        positive_template="positive {x}",
        negative_template="negative {x}",
        slots=[{"x": f"i{i}"} for i in range(n // 2)],
    )
    ds = PrincipleContrastiveBuilder([spec]).build("PF-test")
    cap = MockActivationCapturer(
        hidden_size=hidden_size, noise_std=0.05, signal_strength=2.0
    )
    return cap.capture(ds, layers=[0])[0]


def test_compute_steering_vector_is_unit_norm_by_default() -> None:
    batch = _separable_batch()
    v = compute_steering_vector(batch, "PF-test")
    assert isinstance(v, SteeringVector)
    assert v.hidden_size == batch.activations.shape[1]
    assert v.vector.dtype == np.float32
    assert v.magnitude > 0
    assert pytest.approx(np.linalg.norm(v.vector), abs=1e-5) == 1.0


def test_compute_steering_vector_rejects_single_class() -> None:
    acts = np.zeros((4, 8), dtype=np.float32)
    labels = np.array([True, True, True, True])
    batch = ActivationBatch(
        layer=0,
        hook_name="resid_post",
        activations=acts,
        labels=labels,
        prompt_ids=["a", "b", "c", "d"],
    )
    with pytest.raises(ValueError, match="at least one"):
        compute_steering_vector(batch, "PF-test")


def test_steering_vector_points_from_neg_to_pos() -> None:
    """Adding the vector to the negative mean should move it toward the positive mean."""
    batch = _separable_batch()
    v = compute_steering_vector(batch, "PF-test", normalize=False)
    neg_mean = batch.activations[~batch.labels].mean(0)
    pos_mean = batch.activations[batch.labels].mean(0)
    # v == pos_mean - neg_mean by construction
    np.testing.assert_allclose(neg_mean + v.vector, pos_mean, atol=1e-5)


def test_apply_steering_changes_residual() -> None:
    batch = _separable_batch()
    v = compute_steering_vector(batch, "PF-test")
    resid = np.zeros(v.hidden_size, dtype=np.float32)
    steered = apply_steering_to_residual(resid, v, alpha=2.5)
    np.testing.assert_allclose(steered, 2.5 * v.vector)


def test_apply_steering_broadcasts_over_batch() -> None:
    batch = _separable_batch()
    v = compute_steering_vector(batch, "PF-test")
    arr = np.zeros((5, v.hidden_size), dtype=np.float32)
    steered = apply_steering_to_residual(arr, v, alpha=1.0)
    for row in steered:
        np.testing.assert_allclose(row, v.vector)


def test_project_out_removes_component_along_vector() -> None:
    batch = _separable_batch()
    v = compute_steering_vector(batch, "PF-test")
    # After projection, dot with v should be ~0 for each row
    projected = project_out(batch.activations, v)
    dots = projected @ v.vector
    np.testing.assert_allclose(dots, 0.0, atol=1e-5)


def test_evaluate_steering_effect_with_probe_monotone_in_alpha() -> None:
    """Positive alpha should push probe scores higher; negative alpha lower."""
    batch = _separable_batch(n=60)
    v = compute_steering_vector(batch, "PF-test")
    probe = LinearProbe(principle_id="PF-test", layer=0, hook_name="resid_post")
    probe.fit(batch.activations, batch.labels)

    # Use the vector with its original magnitude for steering, since unit
    # vectors are tiny relative to the activation scale.
    big_v = SteeringVector(
        principle_id=v.principle_id,
        layer=v.layer,
        hook_name=v.hook_name,
        vector=(v.vector * v.magnitude).astype(np.float32),
        magnitude=v.magnitude,
        n_positive=v.n_positive,
        n_negative=v.n_negative,
    )

    base = evaluate_steering_effect(batch, big_v, probe.predict_proba, alpha=0.0)
    plus = evaluate_steering_effect(batch, big_v, probe.predict_proba, alpha=+1.0)
    minus = evaluate_steering_effect(batch, big_v, probe.predict_proba, alpha=-1.0)

    # Mean probe confidence across negatives should rise with positive alpha
    # and fall with negative alpha.
    assert plus.probe_score_negative > base.probe_score_negative
    assert minus.probe_score_negative < base.probe_score_negative


def test_compute_steering_vectors_for_principle_one_per_layer() -> None:
    spec = ContrastiveSpec(
        principle_id="PF-test",
        positive_template="positive {x}",
        negative_template="negative {x}",
        slots=[{"x": f"{i}"} for i in range(30)],
    )
    ds = PrincipleContrastiveBuilder([spec]).build("PF-test")
    cap = MockActivationCapturer(hidden_size=24)
    batches = cap.capture(ds, layers=[0, 5, 10])
    vectors = compute_steering_vectors_for_principle(batches, "PF-test")
    assert [v.layer for v in vectors] == [0, 5, 10]
    for v in vectors:
        assert v.hidden_size == 24
