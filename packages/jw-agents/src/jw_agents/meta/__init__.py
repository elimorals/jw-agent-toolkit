"""jw_agents.meta — meta-orchestrator over existing procedural agents (Fase 65).

Public API:
    from jw_agents.meta import (
        MetaOrchestrator,
        OrchestrationPlan, OrchestrationResult,
        Step, StepResult, CritiqueVerdict,
        register_tool, list_tools, get_tool, ToolNotFound,
    )
"""

from __future__ import annotations

from jw_agents.meta.models import (
    CritiqueVerdict,
    OrchestrationPlan,
    OrchestrationResult,
    Step,
    StepResult,
)
from jw_agents.meta.orchestrator import MetaOrchestrator
from jw_agents.meta.registry import (
    ToolNotFound,
    discover_plugin_tools,
    get_tool,
    list_tools,
    register_tool,
)

__all__ = [
    "CritiqueVerdict",
    "MetaOrchestrator",
    "OrchestrationPlan",
    "OrchestrationResult",
    "Step",
    "StepResult",
    "ToolNotFound",
    "discover_plugin_tools",
    "get_tool",
    "list_tools",
    "register_tool",
]
