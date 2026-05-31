"""Programmatic entry point used by both jw-cli and CI.

The real Typer command is in jw-cli (it wires this into the `jw` umbrella).
"""

from __future__ import annotations

import asyncio
import inspect
from collections.abc import Callable
from pathlib import Path
from typing import Any

from jw_eval.models import LayerName, SuiteReport
from jw_eval.suite import Suite


def _make_sync_wrapper(fn: Callable[..., Any]) -> Callable[[dict[str, Any]], Any]:
    """Wrap an async or sync agent into a sync callable accepting one dict."""

    if inspect.iscoroutinefunction(fn):

        def call(inp: dict[str, Any]) -> Any:
            return asyncio.run(fn(**inp))

        return call

    def call(inp: dict[str, Any]) -> Any:
        return fn(**inp)

    return call


def default_agent_registry() -> dict[str, Callable[[dict[str, Any]], Any]]:
    """Return the registry of real agents from jw-agents wrapped for sync invocation.

    Each entry accepts the GoldenCase.input dict and returns the agent's
    AgentResult. Async agents are wrapped via asyncio.run.
    """

    from jw_agents.apologetics import apologetics  # type: ignore[import-not-found]
    from jw_agents.conversation_assistant import conversation_assistant  # type: ignore[import-not-found]
    from jw_agents.life_topics import life_topics  # type: ignore[import-not-found]
    from jw_agents.meeting_helper import meeting_helper  # type: ignore[import-not-found]
    from jw_agents.research_topic import research_topic  # type: ignore[import-not-found]
    from jw_agents.verse_explainer import verse_explainer  # type: ignore[import-not-found]

    registry: dict[str, Callable[[dict[str, Any]], Any]] = {
        "apologetics": _make_sync_wrapper(apologetics),
        "conversation_assistant": _make_sync_wrapper(conversation_assistant),
        "life_topics": _make_sync_wrapper(life_topics),
        "meeting_helper": _make_sync_wrapper(meeting_helper),
        "research_topic": _make_sync_wrapper(research_topic),
        "verse_explainer": _make_sync_wrapper(verse_explainer),
    }
    return registry


def run_from_cli(
    cases_root: Path,
    snapshots_root: Path,
    layers: list[LayerName],
    agent_filter: str | None = None,
    live: bool = False,
    agent_registry: dict[str, Callable[[dict[str, Any]], Any]] | None = None,
) -> SuiteReport:
    suite = Suite(
        cases_root=cases_root,
        snapshots_root=snapshots_root,
        agent_registry=agent_registry or default_agent_registry(),
    )
    return suite.run(layers=layers, agent_filter=agent_filter, live=live)
