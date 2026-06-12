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
from jw_interp.probe_store import (
    ProbeStoreManifest,
    RuntimeProbe,
    load_probe,
    load_probe_set,
    save_probe,
    save_probe_set,
)
from jw_interp.probing import (
    LinearProbe,
    train_probe,
    train_probes_for_principle,
)
from jw_interp.runtime import (
    ProbeEvaluator,
    ProbeEvaluatorCallable,
    build_probe_evaluator,
    mock_evaluator,
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
    if name in ("GemmaScopeSAE", "load_gemma_scope_sae", "summarize_gemma_features"):
        from jw_interp.gemma_scope import (
            GemmaScopeSAE,
            load_gemma_scope_sae,
            summarize_gemma_features,
        )
        return {
            "GemmaScopeSAE": GemmaScopeSAE,
            "load_gemma_scope_sae": load_gemma_scope_sae,
            "summarize_gemma_features": summarize_gemma_features,
        }[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "ActivationBatch",
    "ContrastivePair",
    "ContrastiveSpec",
    "FeatureActivationSummary",
    "GemmaScopeSAE",
    "LinearProbe",
    "PatchedActivation",
    "PatchingEffect",
    "PrincipleContrastiveBuilder",
    "ProbeEvaluator",
    "ProbeEvaluatorCallable",
    "ProbeResult",
    "ProbeStoreManifest",
    "ProbingDataset",
    "QwenScopeSAE",
    "RuntimeProbe",
    "SteeringEffect",
    "SteeringVector",
    "TorchActivationCapturer",
    "TorchCaptureConfig",
    "apply_steering_to_residual",
    "build_default_contrastive_specs",
    "build_probe_evaluator",
    "compute_steering_vector",
    "compute_steering_vectors_for_principle",
    "evaluate_patching_effect",
    "evaluate_steering_effect",
    "load_gemma_scope_sae",
    "load_probe",
    "load_probe_set",
    "load_qwen_scope_sae",
    "mock_evaluator",
    "patch_batch",
    "patch_one",
    "project_out",
    "save_probe",
    "save_probe_set",
    "summarize_feature_activations",
    "summarize_gemma_features",
    "train_probe",
    "train_probes_for_principle",
]
