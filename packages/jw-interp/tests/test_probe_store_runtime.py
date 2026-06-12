"""Tests for jw_interp.probe_store and jw_interp.runtime."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from jw_interp.activations import MockActivationCapturer
from jw_interp.contrastive import ContrastiveSpec, PrincipleContrastiveBuilder
from jw_interp.probe_store import (
    PROBE_STORE_VERSION,
    ProbeStoreManifest,
    RuntimeProbe,
    _sigmoid,
    load_probe,
    load_probe_set,
    save_probe,
    save_probe_set,
)
from jw_interp.probing import train_probe
from jw_interp.runtime import ProbeEvaluator, mock_evaluator


def _trained_probe(principle_id: str = "PF001-canon-only", layer: int = 5):
    spec = ContrastiveSpec(
        principle_id=principle_id,
        positive_template="positive {x}",
        negative_template="negative {x}",
        slots=[{"x": f"{i}"} for i in range(30)],
    )
    ds = PrincipleContrastiveBuilder([spec]).build(principle_id)
    cap = MockActivationCapturer(hidden_size=32, noise_std=0.05, signal_strength=2.0)
    batch = cap.capture(ds, layers=[layer])[0]
    return train_probe(batch, principle_id)


# ---------- _sigmoid ----------


def test_sigmoid_matches_reference() -> None:
    x = np.array([-50, -1, 0, 1, 50], dtype=np.float32)
    ref = 1.0 / (1.0 + np.exp(-x.astype(np.float64)))
    np.testing.assert_allclose(_sigmoid(x), ref.astype(np.float32), atol=1e-6)


def test_sigmoid_no_overflow_on_large_values() -> None:
    x = np.array([-1e3, 1e3], dtype=np.float32)
    out = _sigmoid(x)
    assert np.isfinite(out).all()
    assert out[0] == pytest.approx(0.0, abs=1e-6)
    assert out[1] == pytest.approx(1.0, abs=1e-6)


# ---------- save / load ----------


def test_save_probe_creates_npz_and_json(tmp_path: Path) -> None:
    result = _trained_probe()
    out = save_probe(result, tmp_path)
    assert out.exists()
    assert out.suffix == ".npz"
    assert out.with_suffix(".json").exists()


def test_load_probe_round_trips_weights(tmp_path: Path) -> None:
    result = _trained_probe()
    npz = save_probe(result, tmp_path)
    probe = load_probe(npz)
    assert isinstance(probe, RuntimeProbe)
    assert probe.principle_id == result.principle_id
    assert probe.layer == result.layer
    np.testing.assert_allclose(probe.coef, result.coef, atol=1e-6)
    assert probe.bias == pytest.approx(result.bias, abs=1e-6)


def test_runtime_probe_predict_proba_matches_sklearn(tmp_path: Path) -> None:
    """The numpy-only sigmoid path must match sklearn's predict_proba."""
    from sklearn.linear_model import LogisticRegression

    rng = np.random.default_rng(0)
    X = rng.standard_normal((50, 12)).astype(np.float32)
    y = (X[:, 0] > 0).astype(int)
    sk = LogisticRegression(max_iter=1000).fit(X, y)

    probe = RuntimeProbe(
        principle_id="PF-test",
        layer=0,
        hook_name="resid_post",
        coef=sk.coef_.reshape(-1).astype(np.float32),
        bias=float(sk.intercept_[0]),
        accuracy=1.0,
        auc=1.0,
    )
    sk_proba = sk.predict_proba(X)[:, 1]
    rt_proba = probe.predict_proba(X)
    np.testing.assert_allclose(rt_proba, sk_proba.astype(np.float32), atol=1e-5)


def test_save_probe_set_writes_manifest(tmp_path: Path) -> None:
    results = [
        _trained_probe(principle_id="PF001-canon-only", layer=5),
        _trained_probe(principle_id="PF002-cite", layer=12),
    ]
    manifest = ProbeStoreManifest(
        model_name="Qwen/Qwen3.5-0.8B",
        hidden_size=32,
        n_layers=24,
    )
    out_dir = save_probe_set(results, tmp_path, manifest)
    assert (out_dir / "manifest.json").exists()
    probes, m2 = load_probe_set(out_dir)
    assert len(probes) == 2
    assert m2.model_name == "Qwen/Qwen3.5-0.8B"
    assert m2.hidden_size == 32
    assert m2.version == PROBE_STORE_VERSION


def test_load_probe_missing_file_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        load_probe(tmp_path / "nonexistent.npz")


def test_load_probe_set_missing_dir_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        load_probe_set(tmp_path / "nope")


def test_load_probe_set_missing_manifest_raises(tmp_path: Path) -> None:
    (tmp_path / "x.npz").write_bytes(b"\0")
    with pytest.raises(FileNotFoundError, match="manifest.json"):
        load_probe_set(tmp_path)


# ---------- runtime evaluator ----------


def test_mock_evaluator_returns_canned_dict() -> None:
    eval_fn = mock_evaluator({"PF001-canon-only": 0.9, "PF002-cite": 0.3})
    out = eval_fn("anything")
    assert out == {"PF001-canon-only": 0.9, "PF002-cite": 0.3}


def test_probe_evaluator_score_cached() -> None:
    result = _trained_probe(principle_id="PF001", layer=5)
    probe = RuntimeProbe(
        principle_id=result.principle_id,
        layer=result.layer,
        hook_name=result.hook_name,
        coef=result.coef,
        bias=result.bias,
        accuracy=result.accuracy,
        auc=result.auc,
    )
    evaluator = ProbeEvaluator(probes=[probe])
    cached = {5: np.zeros((1, 32), dtype=np.float32)}
    scores = evaluator.score_cached(cached)
    assert "PF001" in scores
    assert 0.0 <= scores["PF001"] <= 1.0


def test_probe_evaluator_call_without_capturer_raises() -> None:
    probe = RuntimeProbe(
        principle_id="PF001",
        layer=5,
        hook_name="resid_post",
        coef=np.zeros(32, dtype=np.float32),
        bias=0.0,
        accuracy=0.5,
        auc=0.5,
    )
    evaluator = ProbeEvaluator(probes=[probe])
    with pytest.raises(RuntimeError, match="no capturer"):
        evaluator("a piece of text")


def test_probe_evaluator_required_layers_is_sorted_unique() -> None:
    probes = [
        RuntimeProbe("PFa", layer=8, hook_name="r", coef=np.zeros(4), bias=0.0,
                     accuracy=0.5, auc=0.5),
        RuntimeProbe("PFb", layer=3, hook_name="r", coef=np.zeros(4), bias=0.0,
                     accuracy=0.5, auc=0.5),
        RuntimeProbe("PFc", layer=8, hook_name="r", coef=np.zeros(4), bias=0.0,
                     accuracy=0.5, auc=0.5),
    ]
    evaluator = ProbeEvaluator(probes=probes)
    assert evaluator.required_layers == [3, 8]


def test_probe_evaluator_score_cached_handles_1d_input() -> None:
    probe = RuntimeProbe(
        principle_id="PF-test",
        layer=0,
        hook_name="resid_post",
        coef=np.ones(8, dtype=np.float32),
        bias=0.0,
        accuracy=0.5,
        auc=0.5,
    )
    evaluator = ProbeEvaluator(probes=[probe])
    cached = {0: np.zeros(8, dtype=np.float32)}  # 1D
    out = evaluator.score_cached(cached)
    assert "PF-test" in out
