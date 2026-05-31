"""jw-gen — generative-content toolkit for personal illustrative use.

Public API (re-exports will land as each module is implemented):
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

__all__: list[str] = []
