"""Tests for jw_interp.probing.

We rely on the mock capturer to produce linearly-separable activations, then
check the probe accuracy is ≥ 0.95 — that's the contract: if probes can't
separate clean synthetic data, the probing pipeline is broken and any later
real-model conclusion would be untrustworthy.
"""

from __future__ import annotations

import numpy as np
import pytest

from jw_interp.activations import MockActivationCapturer
from jw_interp.contrastive import (
    ContrastiveSpec,
    PrincipleContrastiveBuilder,
    build_default_contrastive_specs,
)
from jw_interp.models import ActivationBatch
from jw_interp.probing import LinearProbe, train_probe, train_probes_for_principle


def _bigger_synthetic_dataset(principle_id: str = "PF001-canon-only"):
    """Same principle, more slots so probe has enough samples to train."""
    spec = ContrastiveSpec(
        principle_id=principle_id,
        positive_template="positive prompt about {topic}",
        negative_template="neutral prompt about {topic}",
        slots=[{"topic": f"topic_{i:03d}"} for i in range(40)],
    )
    builder = PrincipleContrastiveBuilder([spec])
    return builder.build(principle_id)


def test_probe_separates_linearly_separable_activations() -> None:
    ds = _bigger_synthetic_dataset()
    cap = MockActivationCapturer(hidden_size=32, noise_std=0.05, signal_strength=2.0)
    batch = cap.capture(ds, layers=[0])[0]
    result = train_probe(batch, "PF001-canon-only")
    assert result.accuracy >= 0.95, (
        f"probe should hit ≥0.95 on linearly-separable synthetic data, "
        f"got {result.accuracy:.3f}"
    )
    assert result.auc >= 0.95


def test_probe_random_activations_near_chance() -> None:
    """Sanity check: probe on pure noise should be near chance (≤ 0.7)."""
    n = 80
    rng = np.random.default_rng(0)
    acts = rng.standard_normal((n, 32)).astype(np.float32)
    labels = rng.integers(0, 2, size=n).astype(bool)
    batch = ActivationBatch(
        layer=0,
        hook_name="resid_post",
        activations=acts,
        labels=labels,
        prompt_ids=[f"p{i}" for i in range(n)],
    )
    result = train_probe(batch, "PF-noise")
    assert result.accuracy <= 0.75, (
        f"probe on random data should be near chance, got {result.accuracy:.3f}"
    )


def test_train_probes_for_principle_returns_one_per_layer() -> None:
    ds = _bigger_synthetic_dataset()
    cap = MockActivationCapturer(hidden_size=32, noise_std=0.05, signal_strength=2.0)
    layers = [0, 4, 8, 12]
    batches = cap.capture(ds, layers=layers)
    results = train_probes_for_principle(batches, "PF001-canon-only")
    assert [r.layer for r in results] == layers
    for r in results:
        assert r.accuracy >= 0.95


def test_probe_coef_has_correct_dimension() -> None:
    ds = _bigger_synthetic_dataset()
    cap = MockActivationCapturer(hidden_size=48, noise_std=0.05, signal_strength=2.0)
    batch = cap.capture(ds, layers=[0])[0]
    result = train_probe(batch, "PF001-canon-only")
    assert result.coef.shape == (48,)
    assert isinstance(result.bias, float)


def test_probe_refuses_to_fit_with_too_few_samples() -> None:
    acts = np.zeros((3, 8), dtype=np.float32)
    labels = np.array([True, False, True])
    batch = ActivationBatch(
        layer=0,
        hook_name="resid_post",
        activations=acts,
        labels=labels,
        prompt_ids=["a", "b", "c"],
    )
    with pytest.raises(ValueError, match="at least 4"):
        train_probe(batch, "PF-test")


def test_probe_predict_proba_works_after_fit() -> None:
    ds = _bigger_synthetic_dataset()
    cap = MockActivationCapturer(hidden_size=32, noise_std=0.05, signal_strength=2.0)
    batch = cap.capture(ds, layers=[0])[0]
    probe = LinearProbe(
        principle_id="PF001-canon-only", layer=0, hook_name="resid_post"
    )
    probe.fit(batch.activations, batch.labels)
    proba = probe.predict_proba(batch.activations)
    assert proba.shape == (batch.activations.shape[0],)
    assert ((proba >= 0.0) & (proba <= 1.0)).all()


def test_end_to_end_default_specs_pipeline() -> None:
    """Full smoke: default specs → capture → probe per principle, all ≥ 0.80."""
    builder = PrincipleContrastiveBuilder(build_default_contrastive_specs())
    cap = MockActivationCapturer(hidden_size=32, noise_std=0.05, signal_strength=2.5)
    # Expand each default ds with synthetic extra pairs so we have ≥ 20 samples
    # (the default seed has only ~4 pairs = 8 samples; not enough for stable
    # accuracy estimates).
    from jw_interp.models import ContrastivePair, ProbingDataset

    for pid in builder.principle_ids:
        base = builder.build(pid)
        extra: list[ContrastivePair] = []
        for i in range(20):
            extra.append(
                ContrastivePair(
                    principle_id=pid,
                    positive=f"synthetic positive {pid} {i}",
                    negative=f"synthetic negative {pid} {i}",
                )
            )
        ds = ProbingDataset(principle_id=pid, pairs=base.pairs + extra)
        batch = cap.capture(ds, layers=[0])[0]
        result = train_probe(batch, pid)
        assert result.accuracy >= 0.85, f"{pid} accuracy {result.accuracy:.3f} < 0.85"
