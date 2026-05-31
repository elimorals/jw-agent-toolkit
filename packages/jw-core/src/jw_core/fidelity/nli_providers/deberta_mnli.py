"""DeBERTaV3MNLI — local transformer NLI via HuggingFace.

Model: ``MoritzLaurer/DeBERTa-v3-large-mnli-fever-anli-ling-wanli`` (Apache-2.0,
~440MB). Multilingual fallback ``MoritzLaurer/mDeBERTa-v3-base-mnli-xnli`` is
selectable via env ``JW_NLI_DEBERTA_MODEL``.

Three targets — auto-detected via ``is_available()``:

  - target="mlx"     : requires ``mlx-transformers`` (Apple Silicon).
  - target="nvidia"  : requires ``torch.cuda.is_available()``.
  - target="cpu"     : always works when ``transformers + torch`` installed.

Lazy load + singleton: the model is downloaded/loaded on the FIRST
``evaluate()`` call, not at ``__init__`` (instantiation must stay cheap so
the factory can probe all three targets without loading anything).

Inference:

  - tokenize as a pair-sequence (premise, claim).
  - softmax 3 logits: [contradiction=0, neutral=1, entailment=2].
  - verdict = argmax label; score = probability of that label.
  - truncation: ``max_length=512``, ``truncation="only_first"`` (preserves the
    shorter ``claim``, recovers room by trimming the ``premise``).
"""

from __future__ import annotations

import logging
import os
import threading
from typing import Any

from jw_core.fidelity.nli import Target
from jw_core.fidelity.verdicts import NLIVerdict, ensure_verdict

logger = logging.getLogger(__name__)

_DEFAULT_MODEL = "MoritzLaurer/DeBERTa-v3-large-mnli-fever-anli-ling-wanli"
_LABELS: tuple[str, str, str] = ("contradicts", "neutral", "entails")


class DeBERTaV3MNLI:
    name = "deberta-v3-mnli"

    def __init__(self, *, target: Target = "cpu") -> None:
        self.target: Target = target
        self._model: Any | None = None
        self._tokenizer: Any | None = None
        self._device: str | None = None
        self._lock = threading.Lock()

    def is_available(self) -> bool:
        # Common: need transformers + torch present.
        try:
            import torch  # noqa: F401
            import transformers  # noqa: F401
        except ImportError:
            return False
        except TypeError:
            # ``monkeypatch.setitem(sys.modules, "transformers", None)`` makes
            # the import raise TypeError; treat as missing.
            return False

        if self.target == "cpu":
            return True
        if self.target == "nvidia":
            try:
                import torch

                return bool(torch.cuda.is_available())
            except Exception:  # noqa: BLE001
                return False
        if self.target == "mlx":
            try:
                import mlx_transformers  # noqa: F401
            except ImportError:
                return False
            return True
        return False

    def _ensure_loaded(self) -> None:
        if self._model is not None and self._tokenizer is not None:
            return
        with self._lock:
            if self._model is not None and self._tokenizer is not None:
                return
            import torch
            from transformers import (
                AutoModelForSequenceClassification,
                AutoTokenizer,
            )

            model_id = os.getenv("JW_NLI_DEBERTA_MODEL", _DEFAULT_MODEL)
            logger.info("Loading DeBERTa NLI model %s (target=%s)", model_id, self.target)

            self._tokenizer = AutoTokenizer.from_pretrained(model_id)
            model = AutoModelForSequenceClassification.from_pretrained(model_id)

            if self.target == "nvidia" and torch.cuda.is_available():
                self._device = "cuda"
            elif self.target == "mlx":
                self._device = "mlx"
            else:
                self._device = "cpu"

            if self._device in {"cpu", "cuda"}:
                model = model.to(self._device)
            # ``model.eval()`` is the PyTorch nn.Module method that switches
            # the model to inference mode (disables dropout / freezes BN),
            # NOT the builtin eval(). No arbitrary code execution.
            model.eval()
            self._model = model

    def evaluate(self, claim: str, premise: str, *, language: str = "en") -> NLIVerdict:
        # Tests can inject ``_tokenizer`` and ``_model`` directly to bypass
        # _ensure_loaded.
        if self._model is None or self._tokenizer is None:
            self._ensure_loaded()
        import torch

        assert self._tokenizer is not None
        assert self._model is not None

        inputs = self._tokenizer(
            premise,
            claim,
            return_tensors="pt",
            truncation="only_first",
            max_length=512,
        )
        if self._device == "cuda":
            inputs = {k: v.to("cuda") for k, v in inputs.items()}

        with torch.no_grad():
            out = self._model(**inputs)
        probs = torch.softmax(out.logits, dim=-1).squeeze(0).tolist()
        idx = int(max(range(3), key=lambda i: probs[i]))
        verdict = _LABELS[idx]
        score = float(probs[idx])

        return ensure_verdict(
            verdict=verdict,
            score=score,
            provider=self.name,
            raw={
                "probs": {
                    "contradicts": round(probs[0], 4),
                    "neutral": round(probs[1], 4),
                    "entails": round(probs[2], 4),
                },
                "target": self.target,
                "device": self._device or "unknown",
                "lang": language,
            },
        )


__all__ = ["DeBERTaV3MNLI"]
