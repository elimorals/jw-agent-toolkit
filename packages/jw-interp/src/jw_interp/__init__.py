"""jw-interp — mechanistic interpretability for JW fine-tuned models.

Public surface:
    - `models`: dataclasses (ContrastivePair, ActivationBatch, ProbeResult, ...)
    - `contrastive`: dataset construction (principle → contrastive pairs)
    - `activations`: capturer interface + mock impl (torch impl in `.torch_capture`)
    - `probing`: linear probe training and evaluation

F80 phase 1 — see docs/superpowers/specs/2026-06-12-fase-80-*.
"""

from jw_interp.contrastive import (
    ContrastiveSpec,
    PrincipleContrastiveBuilder,
    build_default_contrastive_specs,
)
from jw_interp.models import (
    ActivationBatch,
    ContrastivePair,
    ProbeResult,
    ProbingDataset,
)
from jw_interp.patching import (
    PatchedActivation,
    PatchingEffect,
    evaluate_patching_effect,
    patch_batch,
    patch_one,
)
from jw_interp.qwen_scope import (
    FeatureActivationSummary,
    QwenScopeSAE,
    summarize_feature_activations,
)
from jw_interp.probing import (
    LinearProbe,
    train_probe,
    train_probes_for_principle,
)
from jw_interp.steering import (
    SteeringEffect,
    SteeringVector,
    apply_steering_to_residual,
    compute_steering_vector,
    compute_steering_vectors_for_principle,
    evaluate_steering_effect,
    project_out,
)


def __getattr__(name: str):
    """Lazy import of torch-extra symbols so the package imports without torch."""
    if name in ("TorchActivationCapturer", "TorchCaptureConfig"):
        from jw_interp.torch_capture import (
            TorchActivationCapturer,
            TorchCaptureConfig,
        )
        return {"TorchActivationCapturer": TorchActivationCapturer,
                "TorchCaptureConfig": TorchCaptureConfig}[name]
    if name == "load_qwen_scope_sae":
        from jw_interp.qwen_scope import load_qwen_scope_sae
        return load_qwen_scope_sae
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "ActivationBatch",
    "ContrastivePair",
    "ContrastiveSpec",
    "FeatureActivationSummary",
    "LinearProbe",
    "PatchedActivation",
    "PatchingEffect",
    "PrincipleContrastiveBuilder",
    "ProbeResult",
    "ProbingDataset",
    "QwenScopeSAE",
    "SteeringEffect",
    "SteeringVector",
    "TorchActivationCapturer",
    "TorchCaptureConfig",
    "apply_steering_to_residual",
    "build_default_contrastive_specs",
    "compute_steering_vector",
    "compute_steering_vectors_for_principle",
    "evaluate_patching_effect",
    "evaluate_steering_effect",
    "load_qwen_scope_sae",
    "patch_batch",
    "patch_one",
    "project_out",
    "summarize_feature_activations",
    "train_probe",
    "train_probes_for_principle",
]
