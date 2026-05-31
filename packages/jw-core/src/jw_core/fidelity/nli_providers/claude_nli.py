"""ClaudeNLI stub — replaced with full implementation in Task 5."""

from __future__ import annotations

from jw_core.fidelity.nli import Target
from jw_core.fidelity.verdicts import NLIVerdict


class ClaudeNLI:
    name = "claude-nli"
    target: Target = "api"

    def is_available(self) -> bool:
        return False

    def evaluate(self, claim: str, premise: str, *, language: str = "en") -> NLIVerdict:
        raise NotImplementedError("ClaudeNLI not yet wired (Task 5)")
