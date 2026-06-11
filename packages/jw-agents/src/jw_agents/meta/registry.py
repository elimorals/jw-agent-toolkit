"""Tool registry for the meta-orchestrator.

Tools are registered at import time (builtin) or discovered via the
Plugin SDK F41 entry-point group `jw_agent_toolkit.agents`.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from importlib.metadata import entry_points
from typing import Any

from pydantic import BaseModel

logger = logging.getLogger(__name__)

ToolCallable = Callable[..., Awaitable[dict[str, Any]]]


class ToolDescriptor(BaseModel):
    name: str
    description: str
    args_schema: dict[str, str]
    callable_: ToolCallable

    model_config = {"arbitrary_types_allowed": True}


class ToolNotFound(KeyError):
    """Raised when `get_tool(name)` finds nothing."""


_REGISTRY: dict[str, ToolDescriptor] = {}


def register_tool(
    *,
    name: str,
    callable_: ToolCallable,
    description: str,
    args_schema: dict[str, str],
) -> None:
    """Register a tool (or override an existing one with a warning)."""

    if name in _REGISTRY:
        logger.warning("meta: overriding existing tool %r", name)
    _REGISTRY[name] = ToolDescriptor(
        name=name,
        description=description,
        args_schema=args_schema,
        callable_=callable_,
    )


def get_tool(name: str) -> ToolDescriptor:
    """Return the descriptor for `name` or raise `ToolNotFound`."""

    if name not in _REGISTRY:
        raise ToolNotFound(name)
    return _REGISTRY[name]


def list_tools() -> list[ToolDescriptor]:
    """All currently-registered tools, in insertion order."""

    return list(_REGISTRY.values())


def clear_registry() -> None:
    """Reset the registry (for tests only)."""

    _REGISTRY.clear()


def discover_plugin_tools() -> int:
    """Discover tools via Plugin SDK F41 entry-points. Returns count discovered."""

    count = 0
    try:
        eps = entry_points(group="jw_agent_toolkit.agents")
    except Exception as exc:  # noqa: BLE001
        logger.warning("meta: entry_points discovery failed: %s", exc)
        return 0
    for ep in eps:
        try:
            obj = ep.load()
            doc = (getattr(obj, "__doc__", "") or "").strip()
            description = doc.splitlines()[0] if doc else "Plugin tool."
            register_tool(
                name=f"plugin.{ep.name}",
                callable_=obj,
                description=description,
                args_schema={},
            )
            count += 1
        except Exception as exc:  # noqa: BLE001
            logger.warning("meta: failed to load plugin %s: %s", ep.name, exc)
    return count
