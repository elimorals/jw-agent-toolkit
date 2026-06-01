"""Discovery via `importlib.metadata.entry_points`."""

from __future__ import annotations

import logging
import os
from importlib.metadata import EntryPoint, distributions, entry_points

from jw_core.plugins.contracts import EntryPointSpec
from jw_core.plugins.policy import (
    ENV_DISABLED,
    apply_conflict_policy,
    read_env_set,
    read_policy_from_env,
)

logger = logging.getLogger(__name__)


GROUPS: tuple[str, ...] = (
    "jw_agent_toolkit.agents",
    "jw_agent_toolkit.parsers",
    "jw_agent_toolkit.embedders",
    "jw_agent_toolkit.vlm_providers",
    "jw_agent_toolkit.gen_providers",
)


def _entry_points_for_group(group: str) -> list[EntryPoint]:
    """Tiny wrapper for test seam — return list[EntryPoint] for the group."""

    return list(entry_points(group=group))


def _distribution_for_entry_point(ep: EntryPoint) -> tuple[str, str]:
    """Find which distribution declared `ep`.

    Returns (dist_name, dist_version). Falls back to ("unknown", "0.0.0")
    when the EntryPoint was constructed standalone (tests).
    """

    target_module = ep.value.split(":", 1)[0]
    for dist in distributions():
        try:
            dist_eps = list(dist.entry_points)
        except Exception:  # pragma: no cover
            continue
        for d_ep in dist_eps:
            if (
                d_ep.name == ep.name
                and d_ep.group == ep.group
                and d_ep.value.split(":", 1)[0] == target_module
            ):
                return dist.metadata["Name"], dist.metadata["Version"]
    return "unknown", "0.0.0"


def _discover(group: str) -> dict[str, EntryPointSpec]:
    """Discover all plugins for `group` post-policy. Pure: no caching."""

    if os.getenv(ENV_DISABLED, "").strip() == "1":
        return {}

    allow = read_env_set("JW_PLUGINS_ALLOW_LIST")
    deny = read_env_set("JW_PLUGINS_DENY_LIST") or set()
    policy = read_policy_from_env()

    out: dict[str, EntryPointSpec] = {}
    for ep in _entry_points_for_group(group):
        if allow is not None and ep.name not in allow:
            continue
        if ep.name in deny:
            continue
        try:
            module, _, attr = ep.value.partition(":")
            if not module or not attr:
                logger.warning(
                    "skipping malformed entry point %r in group %r (value=%r)",
                    ep.name,
                    group,
                    ep.value,
                )
                continue
            dist_name, dist_version = _distribution_for_entry_point(ep)
            spec = EntryPointSpec(
                name=ep.name,
                group=group,
                module=module,
                attr=attr,
                dist_name=dist_name,
                dist_version=dist_version,
            )
            out = apply_conflict_policy(out, spec, policy)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "failed to register plugin %r in group %r: %s", ep.name, group, exc
            )
    return out
