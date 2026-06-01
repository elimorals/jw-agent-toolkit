"""Conflict policies + env-var helpers."""

from __future__ import annotations

import logging
import os
from enum import StrEnum

from jw_core.plugins.contracts import EntryPointSpec
from jw_core.plugins.errors import PluginConflictError

logger = logging.getLogger(__name__)


class ConflictPolicy(StrEnum):
    """How to behave when two plugins register the same name in the same group."""

    FIRST_WINS = "first_wins"
    LAST_WINS = "last_wins"
    NAMESPACED = "namespaced"
    REJECT = "reject"


ENV_POLICY = "JW_PLUGINS_CONFLICT_POLICY"
ENV_ALLOW = "JW_PLUGINS_ALLOW_LIST"
ENV_DENY = "JW_PLUGINS_DENY_LIST"
ENV_DISABLED = "JW_PLUGINS_DISABLED"
ENV_STRICT = "JW_PLUGINS_STRICT"


def read_env_set(var: str) -> set[str] | None:
    """Parse a CSV env var. Missing or empty → None (no filter)."""

    raw = os.getenv(var, "").strip()
    if not raw:
        return None
    return {piece.strip() for piece in raw.split(",") if piece.strip()}


def read_policy_from_env() -> ConflictPolicy:
    """Resolve the conflict policy from env; default NAMESPACED."""

    raw = os.getenv(ENV_POLICY, "").strip().lower()
    if not raw:
        return ConflictPolicy.NAMESPACED
    try:
        return ConflictPolicy(raw)
    except ValueError:
        logger.warning(
            "ignoring invalid %s=%r — falling back to NAMESPACED", ENV_POLICY, raw
        )
        return ConflictPolicy.NAMESPACED


def apply_conflict_policy(
    current: dict[str, EntryPointSpec],
    new: EntryPointSpec,
    policy: ConflictPolicy,
) -> dict[str, EntryPointSpec]:
    """Return an updated mapping after applying `policy` to (current, new)."""

    out = dict(current)
    existing = out.get(new.name)

    if existing is None:
        out[new.name] = new
        return out

    if existing.dist_name == new.dist_name and existing.module == new.module:
        return out

    logger.warning(
        "plugin name conflict in group %s: %r claimed by both %s and %s (policy=%s)",
        new.group,
        new.name,
        existing.dist_name,
        new.dist_name,
        policy.value,
    )

    if policy is ConflictPolicy.FIRST_WINS:
        return out
    if policy is ConflictPolicy.LAST_WINS:
        out[new.name] = new
        return out
    if policy is ConflictPolicy.NAMESPACED:
        out.pop(new.name, None)
        out[existing.namespaced_name] = existing
        out[new.namespaced_name] = new
        return out
    if policy is ConflictPolicy.REJECT:
        raise PluginConflictError(
            name=new.name,
            group=new.group,
            dist_names=(existing.dist_name, new.dist_name),
            policy=policy.value,
        )
    return out  # pragma: no cover
