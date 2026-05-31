"""OllamaNLI stub — replaced with full implementation in Task 7."""

from __future__ import annotations

from jw_core.fidelity.nli import Target
from jw_core.fidelity.verdicts import NLIVerdict


class OllamaNLI:
    name = "ollama-nli"
    target: Target = "cpu"

    def is_available(self) -> bool:
        return False

    def evaluate(self, claim: str, premise: str, *, language: str = "en") -> NLIVerdict:
        raise NotImplementedError("OllamaNLI not yet wired (Task 7)")
