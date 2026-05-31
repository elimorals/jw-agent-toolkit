"""Tests that the public NLIProvider Protocol and Target Literal are exported
and structurally typed correctly.

Spec: docs/superpowers/specs/2026-05-31-fase-39-nli-runtime-design.md §"Provider Protocol".
"""

from __future__ import annotations

from typing import get_args

from jw_core.fidelity import NLIProvider, Target


def test_target_literal_has_four_values() -> None:
    assert set(get_args(Target)) == {"api", "mlx", "nvidia", "cpu"}


def test_nli_provider_is_runtime_checkable() -> None:
    class Stub:
        name = "stub"
        target: Target = "cpu"

        def is_available(self) -> bool:
            return True

        def evaluate(self, claim: str, premise: str, *, language: str = "en"):
            raise NotImplementedError

    assert isinstance(Stub(), NLIProvider)


def test_nli_provider_rejects_missing_method() -> None:
    class Broken:
        name = "broken"
        target: Target = "cpu"

        def is_available(self) -> bool:
            return True

        # no .evaluate()

    assert not isinstance(Broken(), NLIProvider)


def test_public_api_exports_evaluate_entailment_helper() -> None:
    from jw_core.fidelity import evaluate_entailment

    assert callable(evaluate_entailment)
