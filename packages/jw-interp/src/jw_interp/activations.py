"""Activation capture interface + deterministic mock.

The capture step takes a list of prompt texts, runs them through some model,
and returns one ``ActivationBatch`` per (layer, hook). The mock implementation
generates linearly-separable activations from the (text, label) pair so probe
training can be tested end-to-end without torch.

The torch implementation lives in ``torch_capture`` (optional, requires the
``torch`` extra) and is imported lazily.
"""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from typing import Protocol

import numpy as np

from jw_interp.models import ActivationBatch, ProbingDataset


class ActivationCapturer(Protocol):
    """Captures activations for a dataset of prompts.

    Implementations must return one ``ActivationBatch`` per layer requested,
    in input order matching ``dataset.flat_prompts()``.
    """

    def capture(
        self,
        dataset: ProbingDataset,
        *,
        layers: Sequence[int],
        hook_name: str = "resid_post",
    ) -> list[ActivationBatch]: ...


class MockActivationCapturer:
    """Deterministic synthetic capturer for testing and dry-runs.

    Generates activations from a hash of (prompt, layer, hook) so calls
    are reproducible. By construction, positive prompts have an offset
    vector added to their activation, making the dataset *linearly
    separable*. This lets us write a TDD probe test that must hit
    ≥ 0.95 accuracy or the probing pipeline is broken.

    Args:
      hidden_size: dimensionality of the synthetic residual stream.
      noise_std: noise added to each activation (set very low to keep
        the synthetic dataset clean — separability is the contract).
      signal_strength: magnitude of the positive-class offset.
      seed: base seed; per-prompt seed is derived deterministically.
    """

    def __init__(
        self,
        *,
        hidden_size: int = 64,
        noise_std: float = 0.05,
        signal_strength: float = 2.0,
        seed: int = 17,
    ) -> None:
        self.hidden_size = hidden_size
        self.noise_std = noise_std
        self.signal_strength = signal_strength
        self.seed = seed

    def _direction_for(self, principle_id: str, layer: int, hook_name: str) -> np.ndarray:
        """One stable offset direction per (principle, layer, hook).

        We use sha256 of the key as a deterministic seed so the direction
        is reproducible across runs and processes.
        """
        key = f"{principle_id}::layer{layer}::{hook_name}::{self.seed}"
        digest = hashlib.sha256(key.encode("utf-8")).digest()
        seed = int.from_bytes(digest[:8], "big") % (2**32 - 1)
        rng = np.random.default_rng(seed)
        direction = rng.standard_normal(self.hidden_size).astype(np.float32)
        direction /= np.linalg.norm(direction) + 1e-9
        return direction

    def _base_for_prompt(self, prompt_id: str, layer: int, hook_name: str) -> np.ndarray:
        key = f"{prompt_id}::layer{layer}::{hook_name}::{self.seed}::base"
        digest = hashlib.sha256(key.encode("utf-8")).digest()
        seed = int.from_bytes(digest[:8], "big") % (2**32 - 1)
        rng = np.random.default_rng(seed)
        return rng.standard_normal(self.hidden_size).astype(np.float32) * self.noise_std

    def capture(
        self,
        dataset: ProbingDataset,
        *,
        layers: Sequence[int],
        hook_name: str = "resid_post",
    ) -> list[ActivationBatch]:
        prompts = dataset.flat_prompts()
        n = len(prompts)
        labels = np.array([is_pos for _, is_pos, _ in prompts], dtype=bool)
        prompt_ids = [pid for _, _, pid in prompts]

        out: list[ActivationBatch] = []
        for layer in layers:
            direction = self._direction_for(dataset.principle_id, layer, hook_name)
            acts = np.zeros((n, self.hidden_size), dtype=np.float32)
            for i, (_text, is_pos, pid) in enumerate(prompts):
                base = self._base_for_prompt(pid, layer, hook_name)
                acts[i] = base + (self.signal_strength * direction if is_pos else 0.0)
            out.append(
                ActivationBatch(
                    layer=layer,
                    hook_name=hook_name,
                    activations=acts,
                    labels=labels,
                    prompt_ids=prompt_ids,
                )
            )
        return out


def _torch_capturer_unavailable_msg() -> str:
    return (
        "Torch-based ActivationCapturer requires the `torch` extra. Install with:\n"
        "    uv sync --extra torch\n"
        "Or instantiate `jw_interp.activations.MockActivationCapturer` for a "
        "deterministic synthetic capturer."
    )


def load_torch_capturer():  # pragma: no cover - thin re-export
    """Lazy loader for the torch-backed capturer. Optional dep."""
    try:
        from jw_interp.torch_capture import TorchActivationCapturer
    except ImportError as exc:
        raise ImportError(_torch_capturer_unavailable_msg()) from exc
    return TorchActivationCapturer
