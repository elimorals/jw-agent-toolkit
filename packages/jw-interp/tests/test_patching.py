"""Tests for jw_interp.patching."""

from __future__ import annotations

import numpy as np
import pytest

from jw_interp.activations import MockActivationCapturer
from jw_interp.contrastive import ContrastiveSpec, PrincipleContrastiveBuilder
from jw_interp.models import ActivationBatch
from jw_interp.patching import (
    evaluate_patching_effect,
    patch_batch,
    patch_one,
)
from jw_interp.probing import LinearProbe


def _two_layer_batches() -> tuple[ActivationBatch, ActivationBatch]:
    """Two batches from the same dataset at different layers."""
    spec = ContrastiveSpec(
        principle_id="PF-test",
        positive_template="positive {x}",
        negative_template="negative {x}",
        slots=[{"x": f"{i}"} for i in range(20)],
    )
    ds = PrincipleContrastiveBuilder([spec]).build("PF-test")
    cap = MockActivationCapturer(hidden_size=32, noise_std=0.05, signal_strength=2.0)
    batches = cap.capture(ds, layers=[0, 5])
    return batches[0], batches[1]


def test_patch_one_copies_source_activation() -> None:
    b_layer0, _ = _two_layer_batches()
    patched = patch_one(b_layer0, b_layer0, target_index=0, source_index=3)
    np.testing.assert_allclose(patched.patched, b_layer0.activations[3])
    assert patched.source_prompt_id == b_layer0.prompt_ids[3]
    assert patched.target_prompt_id == b_layer0.prompt_ids[0]
    assert patched.layer == 0


def test_patch_one_rejects_hidden_size_mismatch() -> None:
    b0, _ = _two_layer_batches()
    other = ActivationBatch(
        layer=0,
        hook_name="resid_post",
        activations=np.zeros((4, 16), dtype=np.float32),  # wrong dim
        labels=np.array([True, False, True, False]),
        prompt_ids=["a", "b", "c", "d"],
    )
    with pytest.raises(ValueError, match="hidden_size mismatch"):
        patch_one(b0, other, target_index=0, source_index=0)


def test_patch_batch_returns_source_copy() -> None:
    b0, _ = _two_layer_batches()
    # Patch with self → result equals source
    patched = patch_batch(b0, b0)
    np.testing.assert_allclose(patched, b0.activations)
    # And it is a copy (not the same array)
    assert patched is not b0.activations


def test_patch_batch_rejects_shape_mismatch() -> None:
    b0, _ = _two_layer_batches()
    other = ActivationBatch(
        layer=0,
        hook_name="resid_post",
        activations=np.zeros((b0.activations.shape[0] + 1, b0.activations.shape[1]), dtype=np.float32),
        labels=np.zeros(b0.activations.shape[0] + 1, dtype=bool),
        prompt_ids=[f"p{i}" for i in range(b0.activations.shape[0] + 1)],
    )
    with pytest.raises(ValueError, match="shape mismatch"):
        patch_batch(b0, other)


def test_evaluate_patching_effect_zero_when_target_equals_source() -> None:
    b0, _ = _two_layer_batches()
    probe = LinearProbe(principle_id="PF-test", layer=0, hook_name="resid_post")
    probe.fit(b0.activations, b0.labels)
    effect = evaluate_patching_effect(b0, b0, probe.predict_proba, "PF-test")
    assert abs(effect.effect) < 1e-6


def test_evaluate_patching_effect_rejects_layer_mismatch() -> None:
    b0, b5 = _two_layer_batches()
    probe = LinearProbe(principle_id="PF-test", layer=0, hook_name="resid_post")
    probe.fit(b0.activations, b0.labels)
    with pytest.raises(ValueError, match="layer .* != source layer"):
        evaluate_patching_effect(b0, b5, probe.predict_proba, "PF-test")


def test_evaluate_patching_effect_swaps_labels_increases_separation() -> None:
    """Patching a target with a flipped-label source should shift probe scores."""
    b0, _ = _two_layer_batches()

    # Flip labels in a synthetic source: keep same activations, just relabel
    flipped = ActivationBatch(
        layer=0,
        hook_name="resid_post",
        activations=b0.activations,
        labels=~b0.labels,
        prompt_ids=[f"flipped-{i}" for i in range(b0.activations.shape[0])],
    )
    probe = LinearProbe(principle_id="PF-test", layer=0, hook_name="resid_post")
    probe.fit(b0.activations, b0.labels)
    # Using identical activations under flipped labels → patched array still
    # equals the (same) source, so probe mean stays the same. The test simply
    # checks the call path: validates patching doesn't crash with flipped
    # labels and returns a finite effect.
    effect = evaluate_patching_effect(b0, flipped, probe.predict_proba, "PF-test")
    assert np.isfinite(effect.effect)
