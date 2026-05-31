"""jw-gen — generative-content toolkit for personal illustrative use.

Public API:
    from jw_gen import (
        GenerationRequest,
        GenerationResult,
        WatermarkConfig,
        SafetyDecision,
        get_provider,
        finalize_output,
    )

The policy is LOAD-BEARING. Every output that touches disk MUST pass through
`policy.finalize_output(...)`. Every prompt MUST pass through `safety.evaluate(...)`
before reaching `factory.get_provider(...).generate(...)`.
"""

from jw_gen.factory import get_provider
from jw_gen.models import (
    CostHint,
    GenerationRequest,
    GenerationResult,
    SafetyDecision,
    WatermarkConfig,
)
from jw_gen.policy import finalize_output

__all__ = [
    "CostHint",
    "GenerationRequest",
    "GenerationResult",
    "SafetyDecision",
    "WatermarkConfig",
    "finalize_output",
    "get_provider",
]
