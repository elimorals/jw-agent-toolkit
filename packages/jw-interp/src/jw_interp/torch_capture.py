"""Torch-backed ``ActivationCapturer`` for real HF models.

Uses HuggingFace transformers + native forward hooks. We deliberately avoid
`nnsight` and `transformer_lens` for now:
  - nnsight: extra dep, intervention-graph indirection we don't need for
    pure capture.
  - transformer_lens: would require a port of the target model.

Hooks tap the residual stream at the *output* of the requested decoder
layer (``model.model.layers[i]``). Each prompt is run through the model
once; the activation of the **last input token** at each hooked layer is
pooled (so the resulting batch is shape ``(n_prompts, hidden_size)``).

The torch dep is optional and lazy. If ``torch`` is missing,
``MockActivationCapturer`` from ``jw_interp.activations`` remains usable.

Device selection
----------------
Default device is auto-detected: ``cuda`` → ``mps`` → ``cpu``. M4 Max users
get MPS without configuration; RTX 5090 users get CUDA. Explicit override
via ``device="cpu"`` for deterministic tests.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import numpy as np

from jw_interp.models import ActivationBatch, ProbingDataset

if TYPE_CHECKING:  # pragma: no cover
    import torch
    from transformers import PreTrainedModel, PreTrainedTokenizerBase

logger = logging.getLogger(__name__)


def _auto_device() -> str:
    import torch

    if torch.cuda.is_available():
        return "cuda"
    if torch.backends.mps.is_available():
        return "mps"
    return "cpu"


@dataclass
class TorchCaptureConfig:
    """Capture knobs. Defaults are sane for a 0.8B model on M4 Max."""

    device: str | None = None  # None = auto
    dtype: str = "float32"     # "float32" | "float16" | "bfloat16"
    max_input_tokens: int = 512
    pooling: str = "last_token"  # "last_token" | "mean"
    trust_remote_code: bool = False


class TorchActivationCapturer:
    """Capture residual-stream activations from any HF causal LM.

    Construction is lazy: the model + tokenizer are loaded on first
    ``capture()`` call so users can build the capturer without paying
    the model-load cost when they're only running mock tests.
    """

    def __init__(
        self,
        model_name_or_path: str,
        *,
        config: TorchCaptureConfig | None = None,
    ) -> None:
        self.model_name_or_path = model_name_or_path
        self.config = config or TorchCaptureConfig()
        self._model: Any = None
        self._tokenizer: Any = None
        self._device: str | None = None
        self._hidden_size: int | None = None
        self._n_layers: int | None = None

    # ---------- model lifecycle ----------

    def _ensure_loaded(self) -> None:
        if self._model is not None:
            return
        try:
            import torch
            from transformers import AutoModelForCausalLM, AutoTokenizer
        except ImportError as exc:  # pragma: no cover
            raise ImportError(
                "TorchActivationCapturer requires `torch` + `transformers`. "
                "Install with: uv sync --extra torch"
            ) from exc

        self._device = self.config.device or _auto_device()
        dtype_map = {
            "float32": torch.float32,
            "float16": torch.float16,
            "bfloat16": torch.bfloat16,
        }
        dtype = dtype_map.get(self.config.dtype, torch.float32)

        logger.info(
            "Loading %s on device=%s dtype=%s",
            self.model_name_or_path,
            self._device,
            self.config.dtype,
        )
        self._tokenizer = AutoTokenizer.from_pretrained(
            self.model_name_or_path,
            trust_remote_code=self.config.trust_remote_code,
        )
        if self._tokenizer.pad_token is None:
            self._tokenizer.pad_token = self._tokenizer.eos_token

        self._model = AutoModelForCausalLM.from_pretrained(
            self.model_name_or_path,
            torch_dtype=dtype,
            trust_remote_code=self.config.trust_remote_code,
        )
        self._model.to(self._device)
        self._model.eval()

        # Discover hidden size and layer count from the model config
        cfg = self._model.config
        self._hidden_size = int(getattr(cfg, "hidden_size", 0))
        self._n_layers = int(
            getattr(cfg, "num_hidden_layers", getattr(cfg, "n_layer", 0))
        )
        if not self._hidden_size or not self._n_layers:
            raise RuntimeError(
                f"Could not infer hidden_size / n_layers from "
                f"{self.model_name_or_path}; got hidden_size={self._hidden_size}, "
                f"n_layers={self._n_layers}"
            )

    # ---------- introspection (no model load required) ----------

    @property
    def hidden_size(self) -> int:
        self._ensure_loaded()
        assert self._hidden_size is not None
        return self._hidden_size

    @property
    def n_layers(self) -> int:
        self._ensure_loaded()
        assert self._n_layers is not None
        return self._n_layers

    @property
    def device(self) -> str:
        self._ensure_loaded()
        assert self._device is not None
        return self._device

    # ---------- capture ----------

    def _resolve_layer_modules(self, layers: Sequence[int]):
        """Return the decoder-layer modules to hook.

        Supports the common HF layouts:
          - Qwen / LLaMA-style: ``model.model.layers``
          - GPT-2-style:        ``model.transformer.h``
          - Gemma:              ``model.model.layers``
        """
        m = self._model
        if hasattr(m, "model") and hasattr(m.model, "layers"):
            blocks = m.model.layers
        elif hasattr(m, "transformer") and hasattr(m.transformer, "h"):
            blocks = m.transformer.h
        else:
            raise AttributeError(
                f"Cannot find decoder layers on {type(m).__name__}; "
                "looked at .model.layers and .transformer.h"
            )
        return [blocks[i] for i in layers]

    def _pool(self, hidden: "torch.Tensor", attention_mask: "torch.Tensor") -> "torch.Tensor":
        """Pool sequence dimension to a single vector per row.

        ``hidden`` is ``(batch, seq, dim)``; mask is ``(batch, seq)``.
        """
        if self.config.pooling == "last_token":
            # Find the index of the last non-pad token per row.
            lengths = attention_mask.sum(dim=1) - 1
            idx = lengths.clamp(min=0).long()
            batch_size = hidden.size(0)
            arange = idx.new_tensor(range(batch_size))
            return hidden[arange, idx]
        if self.config.pooling == "mean":
            mask = attention_mask.unsqueeze(-1).type_as(hidden)
            summed = (hidden * mask).sum(dim=1)
            denom = mask.sum(dim=1).clamp(min=1)
            return summed / denom
        raise ValueError(f"Unknown pooling: {self.config.pooling}")

    def capture(
        self,
        dataset: ProbingDataset,
        *,
        layers: Sequence[int],
        hook_name: str = "resid_post",
        batch_size: int = 8,
    ) -> list[ActivationBatch]:
        """Run prompts through the model, return per-layer ``ActivationBatch``."""
        import torch

        self._ensure_loaded()
        assert self._model is not None
        assert self._tokenizer is not None
        assert self._hidden_size is not None

        # Validate layer indices
        bad = [l for l in layers if l < 0 or l >= self.n_layers]
        if bad:
            raise ValueError(
                f"layers {bad} out of range [0, {self.n_layers - 1}] for "
                f"{self.model_name_or_path}"
            )

        flat = dataset.flat_prompts()
        n = len(flat)
        labels = np.array([is_pos for _, is_pos, _ in flat], dtype=bool)
        prompt_ids = [pid for _, _, pid in flat]

        # Allocate output arrays per requested layer
        per_layer: dict[int, np.ndarray] = {
            l: np.zeros((n, self._hidden_size), dtype=np.float32) for l in layers
        }

        # Set up hooks on the requested layers
        modules = self._resolve_layer_modules(layers)
        captured: dict[int, "torch.Tensor"] = {}

        def make_hook(layer_idx: int):
            def _hook(_module, _inputs, output):
                # Decoder-layer modules return either a Tensor or a tuple
                # whose first element is the hidden state.
                t = output[0] if isinstance(output, tuple) else output
                captured[layer_idx] = t
            return _hook

        handles = []
        try:
            for layer_idx, mod in zip(layers, modules, strict=True):
                handles.append(mod.register_forward_hook(make_hook(layer_idx)))

            with torch.inference_mode():
                for start in range(0, n, batch_size):
                    end = min(start + batch_size, n)
                    texts = [flat[i][0] for i in range(start, end)]
                    enc = self._tokenizer(
                        texts,
                        return_tensors="pt",
                        padding=True,
                        truncation=True,
                        max_length=self.config.max_input_tokens,
                    ).to(self._device)
                    captured.clear()
                    self._model(**enc)
                    for layer_idx in layers:
                        hidden = captured.get(layer_idx)
                        if hidden is None:
                            raise RuntimeError(
                                f"Layer {layer_idx} hook did not fire; "
                                "the model layout may differ from expected."
                            )
                        pooled = self._pool(hidden, enc["attention_mask"])
                        per_layer[layer_idx][start:end] = (
                            pooled.detach().to("cpu", torch.float32).numpy()
                        )
        finally:
            for h in handles:
                h.remove()

        return [
            ActivationBatch(
                layer=l,
                hook_name=hook_name,
                activations=per_layer[l],
                labels=labels,
                prompt_ids=prompt_ids,
            )
            for l in layers
        ]
