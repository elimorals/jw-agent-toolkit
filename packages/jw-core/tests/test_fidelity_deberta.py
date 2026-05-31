"""Tests for DeBERTaV3MNLI.

We do NOT download model weights in CI. Tests inject a fake tokenizer/model
pair via direct attribute assignment (``p._tokenizer = ...`` / ``p._model = ...``)
to bypass ``_ensure_loaded``. Integration tests that hit real HuggingFace
weights are gated by the ``nli-local`` extra and only run in nightly.
"""

from __future__ import annotations

import pytest
from jw_core.fidelity.nli_providers.deberta_mnli import DeBERTaV3MNLI


class _FakePipelineOutput:
    """Mimics transformers.AutoModelForSequenceClassification output."""

    def __init__(self, logits) -> None:
        import torch

        self.logits = torch.tensor(logits)


class _FakeTokenizer:
    def __call__(self, premise, hypothesis, return_tensors, truncation, max_length):
        import torch

        return {"input_ids": torch.tensor([[1, 2, 3]])}


class _FakeModel:
    def __init__(self, logits) -> None:
        self.logits = logits

    def __call__(self, **kwargs):
        return _FakePipelineOutput(self.logits)

    def eval(self):
        return self

    def to(self, device):  # noqa: ARG002
        return self


def test_deberta_unavailable_without_transformers(monkeypatch) -> None:
    """If transformers / torch are missing, is_available() must be False."""

    import sys

    monkeypatch.setitem(sys.modules, "transformers", None)
    p = DeBERTaV3MNLI(target="cpu")
    assert p.is_available() is False


def test_deberta_cpu_available_when_transformers_installed() -> None:
    pytest.importorskip("transformers")
    pytest.importorskip("torch")
    p = DeBERTaV3MNLI(target="cpu")
    assert p.is_available() is True


def test_deberta_nvidia_requires_cuda(monkeypatch) -> None:
    pytest.importorskip("torch")
    import torch

    monkeypatch.setattr(torch.cuda, "is_available", lambda: False)
    p = DeBERTaV3MNLI(target="nvidia")
    assert p.is_available() is False


def test_deberta_evaluate_entails_via_injected_model() -> None:
    pytest.importorskip("torch")
    p = DeBERTaV3MNLI(target="cpu")
    # logits[contradiction, neutral, entailment] = [0.1, 0.2, 5.0] → softmax ≈ entailment
    p._tokenizer = _FakeTokenizer()
    p._model = _FakeModel([[0.1, 0.2, 5.0]])
    v = p.evaluate(claim="claim", premise="premise")
    assert v.verdict == "entails"
    assert v.score > 0.9
    assert v.provider == "deberta-v3-mnli"


def test_deberta_evaluate_neutral_via_injected_model() -> None:
    pytest.importorskip("torch")
    p = DeBERTaV3MNLI(target="cpu")
    p._tokenizer = _FakeTokenizer()
    p._model = _FakeModel([[0.1, 5.0, 0.2]])
    v = p.evaluate(claim="claim", premise="premise")
    assert v.verdict == "neutral"


def test_deberta_evaluate_contradicts_via_injected_model() -> None:
    pytest.importorskip("torch")
    p = DeBERTaV3MNLI(target="cpu")
    p._tokenizer = _FakeTokenizer()
    p._model = _FakeModel([[5.0, 0.1, 0.2]])
    v = p.evaluate(claim="claim", premise="premise")
    assert v.verdict == "contradicts"


def test_deberta_lazy_load_caches_singleton() -> None:
    pytest.importorskip("torch")
    p = DeBERTaV3MNLI(target="cpu")
    p._tokenizer = _FakeTokenizer()
    p._model = _FakeModel([[0.1, 0.2, 5.0]])
    # Second call should NOT reload model — check the same instance is reused.
    p.evaluate(claim="a", premise="b")
    same_tokenizer = p._tokenizer
    same_model = p._model
    p.evaluate(claim="c", premise="d")
    assert p._tokenizer is same_tokenizer
    assert p._model is same_model
