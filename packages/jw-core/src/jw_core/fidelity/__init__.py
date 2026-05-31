"""jw_core.fidelity — runtime NLI verification of agent findings.

Public API::

    from jw_core.fidelity import (
        NLIProvider,
        NLIVerdict,
        Target,
        Verdict,
        evaluate_entailment,
        get_default_nli_provider,
        list_available_nli_providers,
    )

Spec: docs/superpowers/specs/2026-05-31-fase-39-nli-runtime-design.md
"""

from __future__ import annotations

from jw_core.fidelity.nli import NLIProvider, Target, evaluate_entailment
from jw_core.fidelity.verdicts import NLIVerdict, Verdict, ensure_verdict

__all__ = [
    "NLIProvider",
    "NLIVerdict",
    "Target",
    "Verdict",
    "ensure_verdict",
    "evaluate_entailment",
    "get_default_nli_provider",
    "list_available_nli_providers",
]


def __getattr__(name: str):
    # Lazy re-exports of factory functions to avoid importing providers at
    # import time (keeps ``import jw_core`` cheap on hosts without transformers).
    if name == "get_default_nli_provider":
        from jw_core.fidelity.factory import get_default_nli_provider as fn

        return fn
    if name == "list_available_nli_providers":
        from jw_core.fidelity.factory import list_available_nli_providers as fn

        return fn
    raise AttributeError(name)
