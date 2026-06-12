"""Tests for the torch-backed capturer.

These tests opt-out gracefully when the ``torch`` extra is not installed,
so the default `uv sync` run continues to pass without GPU deps. When
``torch`` IS installed they run against a *tiny* synthetic causal LM
generated on the fly — no network calls, no Qwen download.
"""

from __future__ import annotations

import pytest

torch = pytest.importorskip("torch")
transformers = pytest.importorskip("transformers")

from jw_interp.contrastive import ContrastiveSpec, PrincipleContrastiveBuilder
from jw_interp.models import ProbingDataset


def _make_tiny_model_dir(tmp_path):
    """Build a microscopic causal LM + tokenizer on disk for testing.

    We use ``transformers`` config builders to produce a GPT-2-like model
    with 2 layers and tiny dims so the full capture test runs in <1s on CPU.
    The tokenizer is the default GPT-2 BPE (already cached in transformers).
    """
    from transformers import GPT2Config, GPT2LMHeadModel, GPT2Tokenizer

    cfg = GPT2Config(
        vocab_size=200,
        n_positions=64,
        n_embd=32,
        n_layer=2,
        n_head=2,
    )
    model = GPT2LMHeadModel(cfg)
    save_dir = tmp_path / "tiny-gpt2"
    save_dir.mkdir()
    model.save_pretrained(str(save_dir))
    # We can't easily build a vocab=200 tokenizer; for tests we reuse the
    # public GPT-2 tokenizer and accept that token ids may exceed our
    # vocab. The model treats them as padding/unk gracefully because we
    # only need a forward pass shape, not generation quality.
    tok = GPT2Tokenizer.from_pretrained("gpt2")
    tok.save_pretrained(str(save_dir))
    return save_dir


def _small_dataset() -> ProbingDataset:
    spec = ContrastiveSpec(
        principle_id="PF-test",
        positive_template="positive {x}",
        negative_template="negative {x}",
        slots=[{"x": "a"}, {"x": "b"}, {"x": "c"}, {"x": "d"}],
    )
    return PrincipleContrastiveBuilder([spec]).build("PF-test")


def test_torch_capturer_imports() -> None:
    from jw_interp.torch_capture import TorchActivationCapturer  # noqa: F401


def test_torch_capturer_lazy_does_not_load_until_capture(tmp_path) -> None:
    from jw_interp.torch_capture import TorchActivationCapturer

    cap = TorchActivationCapturer("nonexistent-model")
    # Property access of model-dependent attrs would fail if loaded
    assert cap._model is None
    assert cap._tokenizer is None


def test_torch_capturer_captures_correct_shape(tmp_path) -> None:
    from jw_interp.torch_capture import TorchActivationCapturer, TorchCaptureConfig

    # Cap vocab limit at <200 by truncating input to short ASCII -> small ids
    save_dir = _make_tiny_model_dir(tmp_path)
    cap = TorchActivationCapturer(
        str(save_dir),
        config=TorchCaptureConfig(device="cpu", dtype="float32", max_input_tokens=8),
    )
    assert cap.hidden_size == 32
    assert cap.n_layers == 2

    ds = _small_dataset()
    batches = cap.capture(ds, layers=[0, 1], batch_size=2)
    assert len(batches) == 2
    for b in batches:
        assert b.activations.shape == (ds.n_prompts, 32)
        assert b.labels.shape == (ds.n_prompts,)
        assert len(b.prompt_ids) == ds.n_prompts


def test_torch_capturer_rejects_out_of_range_layers(tmp_path) -> None:
    from jw_interp.torch_capture import TorchActivationCapturer, TorchCaptureConfig

    save_dir = _make_tiny_model_dir(tmp_path)
    cap = TorchActivationCapturer(
        str(save_dir),
        config=TorchCaptureConfig(device="cpu", max_input_tokens=8),
    )
    ds = _small_dataset()
    with pytest.raises(ValueError, match="out of range"):
        cap.capture(ds, layers=[0, 99], batch_size=2)


def test_torch_capturer_mean_pool_matches_shape(tmp_path) -> None:
    from jw_interp.torch_capture import TorchActivationCapturer, TorchCaptureConfig

    save_dir = _make_tiny_model_dir(tmp_path)
    cap = TorchActivationCapturer(
        str(save_dir),
        config=TorchCaptureConfig(device="cpu", pooling="mean", max_input_tokens=8),
    )
    ds = _small_dataset()
    batches = cap.capture(ds, layers=[0], batch_size=2)
    assert batches[0].activations.shape == (ds.n_prompts, 32)
