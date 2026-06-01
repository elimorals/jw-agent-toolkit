"""Discover BrainDomain instances via F41 plugin SDK."""

from __future__ import annotations

import logging
from typing import Any

try:
    from jw_core.plugins import get_plugins
except ImportError:  # pragma: no cover
    get_plugins = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)


def discover_domains() -> dict[str, Any]:
    """Return name → BrainDomain instance map.

    Always includes 'tj' (builtin). Plugin domains via the F41 entry-point
    group `jw_agent_toolkit.brain_domains` are appended.
    """

    out: dict[str, Any] = {}
    from jw_brain.domain.builtin_tj import TJBrainDomain

    out["tj"] = TJBrainDomain()

    if get_plugins is None:
        return out

    try:
        plugins = get_plugins("jw_agent_toolkit.brain_domains")
    except Exception as exc:  # noqa: BLE001
        logger.warning("failed to discover brain_domain plugins: %s", exc)
        return out

    for name, spec in plugins.items():
        try:
            target = spec.resolve()
            instance = target() if isinstance(target, type) else target
        except Exception as exc:  # noqa: BLE001
            logger.warning("plugin domain %r failed to load: %s", name, exc)
            continue
        # name lookup priority: instance.name > spec.name
        domain_name = getattr(instance, "name", None) or name
        if domain_name in out:
            logger.warning(
                "plugin domain %r conflicts with existing %r; keeping existing",
                domain_name,
                domain_name,
            )
            continue
        out[domain_name] = instance
    return out
