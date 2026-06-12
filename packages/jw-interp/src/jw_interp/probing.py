"""Linear probe training and per-principle multi-layer evaluation.

A probe at one (principle, layer, hook) is a logistic-regression classifier
on the activations. We:
  - hold out 20% as a stratified test split,
  - report ``accuracy`` and ``auc`` on the test split,
  - keep the learned ``coef`` and ``bias`` so F80.2 (steering) can reuse them
    as a direction vector.

We chose sklearn over torch on purpose: probes are tiny linear models and the
sklearn API is fast, stable, and dependency-light. Activations come from
whatever produced the ``ActivationBatch`` (mock or real model).
"""

from __future__ import annotations

import logging
import warnings
from typing import Sequence

import numpy as np
from sklearn.exceptions import ConvergenceWarning
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import train_test_split

from jw_interp.models import ActivationBatch, ProbeResult

logger = logging.getLogger(__name__)


class LinearProbe:
    """Thin wrapper around `sklearn.linear_model.LogisticRegression`.

    Kept as a class (not a free fn) so callers can persist a trained probe
    and call ``.score(activations)`` later without re-fitting. Each instance
    is bound to a specific (principle, layer, hook).
    """

    def __init__(
        self,
        *,
        principle_id: str,
        layer: int,
        hook_name: str,
        C: float = 1.0,
        max_iter: int = 1000,
        random_state: int = 0,
    ) -> None:
        self.principle_id = principle_id
        self.layer = layer
        self.hook_name = hook_name
        self._model = LogisticRegression(
            C=C,
            max_iter=max_iter,
            random_state=random_state,
            n_jobs=1,
        )
        self._converged: bool = False
        self._n_train: int = 0
        self._n_test: int = 0
        self._test_acc: float = float("nan")
        self._test_auc: float = float("nan")

    @property
    def coef(self) -> np.ndarray:
        """The learned weight vector. Shape ``(hidden_size,)``."""
        if not hasattr(self._model, "coef_"):
            raise RuntimeError("Probe not yet fit; call .fit() first.")
        return self._model.coef_.reshape(-1).astype(np.float32)

    @property
    def bias(self) -> float:
        if not hasattr(self._model, "intercept_"):
            raise RuntimeError("Probe not yet fit; call .fit() first.")
        return float(self._model.intercept_[0])

    def fit(
        self,
        activations: np.ndarray,
        labels: np.ndarray,
        *,
        test_size: float = 0.2,
        random_state: int = 0,
    ) -> ProbeResult:
        """Fit on a stratified split. Returns ``ProbeResult`` for this layer."""
        if activations.shape[0] != labels.shape[0]:
            raise ValueError(
                f"activations rows ({activations.shape[0]}) != labels ({labels.shape[0]})"
            )
        if activations.shape[0] < 4:
            raise ValueError(
                f"Need at least 4 samples for a stratified probe fit, got "
                f"{activations.shape[0]}"
            )

        X_tr, X_te, y_tr, y_te = train_test_split(
            activations,
            labels,
            test_size=test_size,
            stratify=labels,
            random_state=random_state,
        )
        with warnings.catch_warnings(record=True) as warn_list:
            warnings.simplefilter("always", ConvergenceWarning)
            self._model.fit(X_tr, y_tr)
            self._converged = not any(
                issubclass(w.category, ConvergenceWarning) for w in warn_list
            )

        self._n_train = int(X_tr.shape[0])
        self._n_test = int(X_te.shape[0])
        self._test_acc = float(self._model.score(X_te, y_te))
        # AUC requires both classes present in the test split — guaranteed by
        # stratified split as long as both classes exist in the input.
        if len(np.unique(y_te)) >= 2:
            proba = self._model.predict_proba(X_te)[:, 1]
            self._test_auc = float(roc_auc_score(y_te, proba))
        else:
            logger.debug(
                "AUC undefined for probe %s/L%d: test split has one class only",
                self.principle_id,
                self.layer,
            )
            self._test_auc = float("nan")

        return ProbeResult(
            principle_id=self.principle_id,
            layer=self.layer,
            hook_name=self.hook_name,
            accuracy=self._test_acc,
            auc=self._test_auc,
            n_train=self._n_train,
            n_test=self._n_test,
            coef=self.coef,
            bias=self.bias,
            convergence="converged" if self._converged else "not-converged",
        )

    def predict_proba(self, activations: np.ndarray) -> np.ndarray:
        """Positive-class probability for each row of ``activations``."""
        return self._model.predict_proba(activations)[:, 1]


def train_probe(
    batch: ActivationBatch,
    principle_id: str,
    *,
    C: float = 1.0,
    test_size: float = 0.2,
    random_state: int = 0,
) -> ProbeResult:
    """Convenience: train a single probe on one ``ActivationBatch``."""
    probe = LinearProbe(
        principle_id=principle_id,
        layer=batch.layer,
        hook_name=batch.hook_name,
        C=C,
        random_state=random_state,
    )
    return probe.fit(
        batch.activations,
        batch.labels,
        test_size=test_size,
        random_state=random_state,
    )


def train_probes_for_principle(
    batches: Sequence[ActivationBatch],
    principle_id: str,
    *,
    C: float = 1.0,
    test_size: float = 0.2,
    random_state: int = 0,
) -> list[ProbeResult]:
    """Train one probe per layer for a given principle.

    Returns probes in input batch order (typically layer-ordered). Useful
    for producing the (principle × layer) heatmap of probe accuracy.
    """
    return [
        train_probe(
            b,
            principle_id,
            C=C,
            test_size=test_size,
            random_state=random_state,
        )
        for b in batches
    ]
