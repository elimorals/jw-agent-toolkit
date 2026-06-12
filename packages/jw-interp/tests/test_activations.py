"""Tests for jw_interp.activations (mock capturer)."""

from __future__ import annotations

import numpy as np

from jw_interp.activations import MockActivationCapturer
from jw_interp.contrastive import (
    PrincipleContrastiveBuilder,
    build_default_contrastive_specs,
)


def _small_dataset() -> object:
    builder = PrincipleContrastiveBuilder(build_default_contrastive_specs())
    return builder.build("PF001-canon-only")


def test_mock_capturer_returns_one_batch_per_layer() -> None:
    cap = MockActivationCapturer(hidden_size=32)
    ds = _small_dataset()
    batches = cap.capture(ds, layers=[0, 5, 12])  # type: ignore[arg-type]
    assert len(batches) == 3
    assert [b.layer for b in batches] == [0, 5, 12]


def test_mock_capturer_shapes() -> None:
    cap = MockActivationCapturer(hidden_size=64)
    ds = _small_dataset()
    batches = cap.capture(ds, layers=[3])  # type: ignore[arg-type]
    b = batches[0]
    assert b.activations.shape == (ds.n_prompts, 64)  # type: ignore[attr-defined]
    assert b.labels.shape == (ds.n_prompts,)  # type: ignore[attr-defined]
    assert len(b.prompt_ids) == ds.n_prompts  # type: ignore[attr-defined]


def test_mock_capturer_is_deterministic_across_calls() -> None:
    cap = MockActivationCapturer(hidden_size=16, seed=42)
    ds = _small_dataset()
    a = cap.capture(ds, layers=[0])[0]  # type: ignore[arg-type]
    b = cap.capture(ds, layers=[0])[0]  # type: ignore[arg-type]
    np.testing.assert_allclose(a.activations, b.activations)


def test_mock_capturer_positive_negative_separable() -> None:
    """The mock is designed to be linearly separable. Verify the geometry."""
    cap = MockActivationCapturer(
        hidden_size=32, noise_std=0.01, signal_strength=2.0
    )
    ds = _small_dataset()
    batch = cap.capture(ds, layers=[0])[0]  # type: ignore[arg-type]
    pos_mean = batch.activations[batch.labels].mean(axis=0)
    neg_mean = batch.activations[~batch.labels].mean(axis=0)
    diff_norm = float(np.linalg.norm(pos_mean - neg_mean))
    # Mean separation should be near the signal_strength magnitude.
    assert diff_norm > 1.5, (
        f"mock signal too weak: diff_norm={diff_norm:.3f}, expected ~2.0"
    )


def test_mock_capturer_different_principles_use_different_directions() -> None:
    cap = MockActivationCapturer(hidden_size=32, noise_std=0.01)
    builder = PrincipleContrastiveBuilder(build_default_contrastive_specs())
    ds_a = builder.build("PF001-canon-only")
    ds_b = builder.build("PF003-citation-required")
    batch_a = cap.capture(ds_a, layers=[5])[0]
    batch_b = cap.capture(ds_b, layers=[5])[0]
    dir_a = batch_a.activations[batch_a.labels].mean(0) - batch_a.activations[~batch_a.labels].mean(0)
    dir_b = batch_b.activations[batch_b.labels].mean(0) - batch_b.activations[~batch_b.labels].mean(0)
    # Cosine between two different principle directions should be near 0.
    cos = float(
        np.dot(dir_a, dir_b)
        / (np.linalg.norm(dir_a) * np.linalg.norm(dir_b) + 1e-9)
    )
    assert abs(cos) < 0.4, (
        f"different principle directions should be near-orthogonal, cos={cos:.3f}"
    )
