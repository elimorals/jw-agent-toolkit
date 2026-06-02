"""Shared CLI flag installer + target resolver for --trace.

Three target spellings are accepted:
    --trace                 -> "DEFAULT" sentinel -> auto-named file in
                                `$JW_TRACE_DIR` (default `~/.jw-agent-toolkit/traces`)
    --trace /path/to.jsonl  -> explicit path
    --trace -               -> stdout
    (flag absent)           -> NullTraceStore (zero overhead)

CLI authors call:

    target = resolve_trace_target(opt, agent="apologetics")
    tracer = tracer_from_target(target, agent="apologetics")
"""

from __future__ import annotations

import os
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from jw_agents.tracing.store import JsonlTraceStore, NullTraceStore
from jw_agents.tracing.tracer import AgentTracer

DEFAULT_TRACE_DIR_ENV = "JW_TRACE_DIR"
DEFAULT_TRACE_DIR_FALLBACK = "~/.jw-agent-toolkit/traces"


def _default_root() -> Path:
    root = os.environ.get(DEFAULT_TRACE_DIR_ENV) or DEFAULT_TRACE_DIR_FALLBACK
    return Path(root).expanduser()


def _auto_name(agent: str) -> Path:
    day = datetime.now(UTC).strftime("%Y-%m-%d")
    return _default_root() / f"{agent}-{day}-{uuid.uuid4().hex[:8]}.jsonl"


def resolve_trace_target(
    value: str | None,
    *,
    agent: str = "agent",
) -> Path | Literal["-"] | None:
    """Resolve a --trace CLI string into a concrete target.

    Return values:
      None -> tracing disabled (caller must pass to tracer_from_target).
      "-"  -> stdout sentinel.
      Path -> explicit JSONL file (parents created on first write).
    """

    if value is None:
        return None
    if value == "-":
        return "-"
    if value in ("DEFAULT", ""):
        return _auto_name(agent)
    return Path(value).expanduser()


def tracer_from_target(
    target: Path | Literal["-"] | None,
    *,
    agent: str,
) -> AgentTracer:
    """Build an AgentTracer from a resolved --trace target."""

    if target is None:
        return AgentTracer(agent=agent, store=NullTraceStore())
    if target == "-":
        return AgentTracer(agent=agent, store=JsonlTraceStore(path=None))
    return AgentTracer(agent=agent, store=JsonlTraceStore(path=target))
