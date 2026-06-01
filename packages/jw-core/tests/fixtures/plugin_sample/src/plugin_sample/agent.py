"""Agent stub. Returns a deterministic payload."""

from __future__ import annotations

from typing import Any


async def sample_agent(**kwargs: Any) -> dict[str, Any]:
    """Plugin agent — echoes its kwargs."""

    return {"findings": [], "echo": kwargs, "agent": "plugin_sample_agent"}


sample_agent.__name__ = "plugin_sample_agent"
sample_agent.languages = ["en", "es"]  # type: ignore[attr-defined]
sample_agent.version = "0.1.0"  # type: ignore[attr-defined]
