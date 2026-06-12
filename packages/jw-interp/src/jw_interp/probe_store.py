"""Persist and load trained probes for runtime use.

We use plain numpy savez_compressed for the weights and a JSON sidecar for
metadata. This is intentional: joblib pickles arbitrary Python objects (and
re-pickles sklearn internals across versions, which breaks); numpy is
boring, portable, and forward-compatible.

A probe set is a directory::

    probes_dir/
      PF001-canon-only_L12.npz      # weights for one principle × layer
      PF001-canon-only_L12.json     # metadata sidecar
      PF002-...
      manifest.json                 # global metadata (model, hidden_size, ...)

Loading rebuilds a :class:`RuntimeProbe` per principle whose
``predict_proba`` matches the sklearn LogisticRegression sigmoid exactly.
We don't need sklearn at load time, so a runtime that only ships
``numpy + jw-interp`` can still score probes.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from jw_interp.models import ProbeResult

logger = logging.getLogger(__name__)

PROBE_STORE_VERSION = 1


@dataclass(frozen=True)
class RuntimeProbe:
    """A trained probe usable for inference without sklearn.

    Equivalent to the sigmoid of ``X @ coef + bias`` for sklearn's
    LogisticRegression with default settings.
    """

    principle_id: str
    layer: int
    hook_name: str
    coef: np.ndarray  # (hidden_size,)
    bias: float
    accuracy: float
    auc: float

    @property
    def hidden_size(self) -> int:
        return int(self.coef.shape[0])

    def predict_proba(self, activations: np.ndarray) -> np.ndarray:
        """Positive-class probability for each row of ``activations``."""
        if activations.ndim == 1:
            activations = activations[None, :]
        if activations.shape[-1] != self.hidden_size:
            raise ValueError(
                f"activations hidden_size {activations.shape[-1]} != "
                f"probe hidden_size {self.hidden_size}"
            )
        logits = activations @ self.coef + self.bias
        return _sigmoid(logits)


def _sigmoid(x: np.ndarray) -> np.ndarray:
    # Numerically stable sigmoid that avoids overflow warnings on large logits.
    out = np.empty_like(x, dtype=np.float64)
    pos = x >= 0
    out[pos] = 1.0 / (1.0 + np.exp(-x[pos]))
    exp_x = np.exp(x[~pos])
    out[~pos] = exp_x / (1.0 + exp_x)
    return out.astype(np.float32)


@dataclass
class ProbeStoreManifest:
    """Top-level metadata for a probe set."""

    model_name: str
    hidden_size: int
    n_layers: int
    version: int = PROBE_STORE_VERSION
    extra: dict[str, str] = field(default_factory=dict)

    def to_json(self) -> str:
        return json.dumps(
            {
                "model_name": self.model_name,
                "hidden_size": self.hidden_size,
                "n_layers": self.n_layers,
                "version": self.version,
                "extra": self.extra,
            },
            indent=2,
        )

    @classmethod
    def from_json(cls, text: str) -> "ProbeStoreManifest":
        d = json.loads(text)
        return cls(
            model_name=d["model_name"],
            hidden_size=int(d["hidden_size"]),
            n_layers=int(d["n_layers"]),
            version=int(d.get("version", PROBE_STORE_VERSION)),
            extra=d.get("extra", {}),
        )


def _probe_basename(principle_id: str, layer: int) -> str:
    # Filename-safe: spaces become underscores; everything else passes through.
    safe = principle_id.replace("/", "_").replace(" ", "_")
    return f"{safe}_L{layer:02d}"


def save_probe(
    result: ProbeResult,
    probes_dir: str | Path,
) -> Path:
    """Persist a single :class:`ProbeResult` under ``probes_dir``.

    Writes ``<principle>_L<NN>.npz`` (weights) and ``.json`` (metadata).
    Returns the npz path.
    """
    out_dir = Path(probes_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    base = _probe_basename(result.principle_id, result.layer)
    npz_path = out_dir / f"{base}.npz"
    json_path = out_dir / f"{base}.json"

    np.savez_compressed(
        str(npz_path),
        coef=result.coef.astype(np.float32),
        bias=np.array([result.bias], dtype=np.float32),
    )
    json_path.write_text(
        json.dumps(
            {
                "principle_id": result.principle_id,
                "layer": result.layer,
                "hook_name": result.hook_name,
                "accuracy": result.accuracy,
                "auc": result.auc,
                "n_train": result.n_train,
                "n_test": result.n_test,
                "convergence": result.convergence,
                "hidden_size": int(result.coef.shape[0]),
                "version": PROBE_STORE_VERSION,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return npz_path


def load_probe(npz_path: str | Path) -> RuntimeProbe:
    """Load one probe back from disk as a :class:`RuntimeProbe`."""
    p = Path(npz_path)
    json_path = p.with_suffix(".json")
    if not p.exists():
        raise FileNotFoundError(f"Probe weights not found: {p}")
    if not json_path.exists():
        raise FileNotFoundError(f"Probe metadata not found: {json_path}")

    weights = np.load(str(p))
    meta = json.loads(json_path.read_text(encoding="utf-8"))
    return RuntimeProbe(
        principle_id=meta["principle_id"],
        layer=int(meta["layer"]),
        hook_name=meta.get("hook_name", "resid_post"),
        coef=weights["coef"].astype(np.float32),
        bias=float(weights["bias"][0]),
        accuracy=float(meta.get("accuracy", float("nan"))),
        auc=float(meta.get("auc", float("nan"))),
    )


def save_probe_set(
    results: list[ProbeResult],
    probes_dir: str | Path,
    manifest: ProbeStoreManifest,
) -> Path:
    """Persist a whole set of probes + manifest. Returns the dir path."""
    out_dir = Path(probes_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    for r in results:
        save_probe(r, out_dir)
    (out_dir / "manifest.json").write_text(manifest.to_json(), encoding="utf-8")
    return out_dir


def load_probe_set(
    probes_dir: str | Path,
) -> tuple[list[RuntimeProbe], ProbeStoreManifest]:
    """Load all probes + manifest from ``probes_dir``."""
    d = Path(probes_dir)
    if not d.exists():
        raise FileNotFoundError(f"probes_dir does not exist: {d}")
    manifest_path = d / "manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError(f"manifest.json missing in {d}")
    manifest = ProbeStoreManifest.from_json(
        manifest_path.read_text(encoding="utf-8")
    )
    probes: list[RuntimeProbe] = []
    for npz_path in sorted(d.glob("*.npz")):
        probes.append(load_probe(npz_path))
    return probes, manifest
