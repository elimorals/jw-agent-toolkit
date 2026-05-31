"""OpenAINLI stub — replaced with full implementation in Task 6."""

from __future__ import annotations

from jw_core.fidelity.nli import Target
from jw_core.fidelity.verdicts import NLIVerdict


class OpenAINLI:
    name = "openai-nli"
    target: Target = "api"

    def is_available(self) -> bool:
        return False

    def evaluate(self, claim: str, premise: str, *, language: str = "en") -> NLIVerdict:
        raise NotImplementedError("OpenAINLI not yet wired (Task 6)")
