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
from jw_interp.probing import (
    LinearProbe,
    train_probe,
    train_probes_for_principle,
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
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "ActivationBatch",
    "ContrastivePair",
    "ContrastiveSpec",
    "LinearProbe",
    "PrincipleContrastiveBuilder",
    "ProbeResult",
    "ProbingDataset",
    "TorchActivationCapturer",
    "TorchCaptureConfig",
    "build_default_contrastive_specs",
    "train_probe",
    "train_probes_for_principle",
]
