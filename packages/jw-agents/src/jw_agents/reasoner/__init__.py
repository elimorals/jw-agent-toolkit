"""jw_agents.reasoner - doctrinal chain-of-thought with verifiable steps (Fase 67).

Public API:
    from jw_agents.reasoner import (
        ReasoningTree, ReasoningStep, StepKind, Citation,
        NLIStatus, ReasonerConfig,
    )
"""

from __future__ import annotations

from jw_agents.reasoner.models import (
    Citation,
    NLIStatus,
    ReasonerConfig,
    ReasoningStep,
    ReasoningTree,
    StepKind,
)

__all__ = [
    "Citation",
    "NLIStatus",
    "ReasonerConfig",
    "ReasoningStep",
    "ReasoningTree",
    "StepKind",
]
