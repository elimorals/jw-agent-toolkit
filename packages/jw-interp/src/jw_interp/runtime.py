"""Runtime probe evaluator — the bridge into ``jw_agents.fidelity_wrap`` Tier 4.

This module exposes :class:`ProbeEvaluator`: a callable that takes a
piece of text (typically a finding's summary + excerpt) and returns the
positive-class probability for each loaded probe, keyed by principle id.

Two execution paths:

  1. **Eager** (recommended for production): a single
     :class:`jw_interp.TorchActivationCapturer` is held, the text is
     tokenized once, activations at the probes' configured layers are
     captured, and each probe scored. One forward pass per finding.

  2. **Pre-cached** (fast batch): the caller has already captured
     activations and passes a dict ``{layer: (1, hidden)}``; we skip
     the forward pass and just score the probes.

The fidelity_wrap Tier 4 only requires a callable matching
``ProbeEvaluatorCallable``::

    Callable[[str], dict[str, float]]

so users can swap evaluators (mock, eager, pre-cached) without touching
``jw_agents``.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

import numpy as np

from jw_interp.probe_store import RuntimeProbe, load_probe_set

if TYPE_CHECKING:  # pragma: no cover
    from jw_interp.torch_capture import TorchActivationCapturer

logger = logging.getLogger(__name__)


ProbeEvaluatorCallable = Callable[[str], dict[str, float]]


@dataclass
class ProbeEvaluator:
    """Evaluate every loaded probe against a piece of text.

    Holds:
      - ``probes``: list of :class:`RuntimeProbe`.
      - ``capturer``: optional ``TorchActivationCapturer`` for eager mode.
        When ``None``, the evaluator only supports ``.score_cached()``.
      - ``model_name``: kept for tracing/logging.

    Use :func:`build_probe_evaluator` to construct one from a probes
    directory, or instantiate directly with pre-loaded objects.
    """

    probes: list[RuntimeProbe]
    capturer: Any = None  # TorchActivationCapturer (or compatible)
    model_name: str = ""
    _layer_index: dict[int, list[RuntimeProbe]] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        idx: dict[int, list[RuntimeProbe]] = {}
        for p in self.probes:
            idx.setdefault(p.layer, []).append(p)
        self._layer_index = idx

    @property
    def required_layers(self) -> list[int]:
        return sorted(self._layer_index.keys())

    # ---------- eager mode ----------

    def __call__(self, text: str) -> dict[str, float]:
        """Score every probe on ``text`` via the capturer. Returns {principle_id: prob}."""
        if self.capturer is None:
            raise RuntimeError(
                "ProbeEvaluator has no capturer; either pass a capturer at "
                "construction or use .score_cached() with pre-captured activations."
            )
        from jw_interp.contrastive import ContrastiveSpec, PrincipleContrastiveBuilder

        # Build a 1-prompt ProbingDataset by wrapping the text in a trivial
        # spec. The label is irrelevant for inference — only positive rows
        # are kept later.
        spec = ContrastiveSpec(
            principle_id="__runtime__",
            positive_template="{text}",
            negative_template="{text}",
            slots=[{"text": text}],
        )
        dataset = PrincipleContrastiveBuilder([spec]).build("__runtime__")
        # ``flat_prompts()`` yields [positive, negative] both equal to text;
        # only positive_pooled activation feeds the probes.
        batches = self.capturer.capture(
            dataset, layers=self.required_layers
        )
        # For each layer, take the positive row (index 0)
        layer_acts = {b.layer: b.activations[0:1] for b in batches}
        return self._score_layers(layer_acts)

    def score_cached(
        self, cached_activations: dict[int, np.ndarray]
    ) -> dict[str, float]:
        """Score every probe given pre-captured activations.

        ``cached_activations[layer]`` must be shape ``(1, hidden_size)`` or
        ``(hidden_size,)`` for one text.
        """
        normalized: dict[int, np.ndarray] = {}
        for layer, acts in cached_activations.items():
            if acts.ndim == 1:
                acts = acts[None, :]
            normalized[layer] = acts
        return self._score_layers(normalized)

    # ---------- shared ----------

    def _score_layers(self, layer_acts: dict[int, np.ndarray]) -> dict[str, float]:
        out: dict[str, float] = {}
        for layer, probes in self._layer_index.items():
            acts = layer_acts.get(layer)
            if acts is None:
                logger.debug(
                    "No activations captured at layer %d; skipping %d probes",
                    layer,
                    len(probes),
                )
                continue
            for probe in probes:
                proba = probe.predict_proba(acts)[0]
                out[probe.principle_id] = float(proba)
        return out


def build_probe_evaluator(
    *,
    probes_dir: str | Path,
    capturer: "TorchActivationCapturer | None" = None,
    model_name: str | None = None,
) -> ProbeEvaluator:
    """Construct a :class:`ProbeEvaluator` from a probe directory.

    If ``capturer`` is supplied (or ``None`` and the manifest contains a
    ``model_name``, in which case we build one), the resulting evaluator
    is callable in eager mode.
    """
    probes, manifest = load_probe_set(probes_dir)
    resolved_model = model_name or manifest.model_name
    if capturer is None and resolved_model:
        # Lazy build a default capturer. Users who want explicit config can
        # pass it themselves.
        try:
            from jw_interp.torch_capture import (
                TorchActivationCapturer,
                TorchCaptureConfig,
            )
        except ImportError:
            logger.warning(
                "torch extra not installed; built evaluator is cache-only "
                "(use score_cached). Install with: uv sync --extra torch"
            )
            capturer = None
        else:
            capturer = TorchActivationCapturer(
                resolved_model,
                config=TorchCaptureConfig(dtype="float16"),
            )
    return ProbeEvaluator(probes=probes, capturer=capturer, model_name=resolved_model)


def mock_evaluator(returns: dict[str, float]) -> ProbeEvaluatorCallable:
    """Build a :class:`ProbeEvaluatorCallable` that returns a fixed dict.

    Useful for tests of downstream consumers (e.g. fidelity_wrap Tier 4)
    that should not depend on torch / a real model.
    """

    def _eval(_text: str) -> dict[str, float]:
        return dict(returns)

    return _eval
