"""DeBERTaV3MNLI stub — replaced with full implementation in Task 7."""

from __future__ import annotations

from jw_core.fidelity.nli import Target
from jw_core.fidelity.verdicts import NLIVerdict


class DeBERTaV3MNLI:
    name = "deberta-v3-mnli"

    def __init__(self, *, target: Target = "cpu") -> None:
        self.target: Target = target

    def is_available(self) -> bool:
        return False

    def evaluate(self, claim: str, premise: str, *, language: str = "en") -> NLIVerdict:
        raise NotImplementedError("DeBERTaV3MNLI not yet wired (Task 7)")
