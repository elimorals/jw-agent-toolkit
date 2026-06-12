"""Activation patching utilities.

Activation patching answers: "at which layer does the model *decide*
between a faithful answer and a shortcut answer?". The procedure:

  1. Take a contrastive pair ``(prompt_faithful, prompt_shortcut)`` whose
     model outputs differ.
  2. Run the model on ``prompt_faithful``; capture the residual at layer N.
  3. Run the model on ``prompt_shortcut`` while *patching* its layer-N
     residual with the faithful one. Measure output change.
  4. The capa whose patch most changes the output is the decisive layer.

This module provides the **pure-numpy core**: given two ``ActivationBatch``
objects (or pairs of activation vectors), produce patched activations and a
diff. The actual model patching during a forward pass lives in
``torch_patching.py`` (torch extra). The numpy core lets us unit-test the
logic and run it on cached activations without a model.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from jw_interp.models import ActivationBatch


@dataclass(frozen=True)
class PatchedActivation:
    """One patched activation row plus its provenance."""

    source_prompt_id: str
    target_prompt_id: str
    layer: int
    hook_name: str
    patched: np.ndarray  # (hidden_size,) — the target's activation with source patched in


def patch_one(
    target: ActivationBatch,
    source: ActivationBatch,
    *,
    target_index: int,
    source_index: int,
) -> PatchedActivation:
    """Return the source's activation at the target's slot — the simplest patch.

    In a real model forward, you would *replace* the layer-N residual of the
    target prompt with the source prompt's layer-N residual and continue the
    forward pass. Here we just return the source vector + provenance for
    downstream comparison or for caching.
    """
    if target.activations.shape[1] != source.activations.shape[1]:
        raise ValueError(
            f"hidden_size mismatch: target {target.activations.shape[1]} != "
            f"source {source.activations.shape[1]}"
        )
    return PatchedActivation(
        source_prompt_id=source.prompt_ids[source_index],
        target_prompt_id=target.prompt_ids[target_index],
        layer=target.layer,
        hook_name=target.hook_name,
        patched=source.activations[source_index].copy(),
    )


def patch_batch(
    target: ActivationBatch,
    source: ActivationBatch,
) -> np.ndarray:
    """Return a copy of ``target.activations`` with rows replaced by ``source``.

    Both batches must have identical shape and prompt ordering.
    """
    if target.activations.shape != source.activations.shape:
        raise ValueError(
            f"shape mismatch target={target.activations.shape} "
            f"source={source.activations.shape}"
        )
    return source.activations.copy()


@dataclass(frozen=True)
class PatchingEffect:
    """Quantified effect of patching layer N from source into target.

    ``probe_score_before`` is the probe's positive-class confidence on the
    target's original activations; ``probe_score_after`` is after patching.
    ``effect = after − before``; sign indicates direction.
    """

    principle_id: str
    layer: int
    probe_score_before: float
    probe_score_after: float

    @property
    def effect(self) -> float:
        return self.probe_score_after - self.probe_score_before


def evaluate_patching_effect(
    target: ActivationBatch,
    source: ActivationBatch,
    probe_predict_proba,
    principle_id: str,
) -> PatchingEffect:
    """Quantify how much patching shifts the probe score.

    ``target`` and ``source`` must come from the same layer and have the
    same shape. We evaluate the probe before and after the patch and report
    the mean shift.
    """
    if target.layer != source.layer:
        raise ValueError(
            f"target layer {target.layer} != source layer {source.layer}"
        )
    before = float(probe_predict_proba(target.activations).mean())
    after_acts = patch_batch(target, source)
    after = float(probe_predict_proba(after_acts).mean())
    return PatchingEffect(
        principle_id=principle_id,
        layer=target.layer,
        probe_score_before=before,
        probe_score_after=after,
    )
