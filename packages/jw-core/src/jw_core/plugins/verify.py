"""Contract + version verification."""

from __future__ import annotations

import logging
import os
from importlib.metadata import distribution
from typing import Any

from packaging.requirements import Requirement
from packaging.version import Version

import jw_core
from jw_core.plugins.contracts import EntryPointSpec, VerifyReport
from jw_core.plugins.errors import (
    PluginContractError,
    PluginError,
    PluginVersionMismatch,
)
from jw_core.plugins.factory import get_plugins
from jw_core.plugins.policy import ENV_STRICT

logger = logging.getLogger(__name__)


REQUIRED_BY_GROUP: dict[str, tuple[str, ...]] = {
    "jw_agent_toolkit.agents": ("__call__",),
    "jw_agent_toolkit.parsers": ("__call__",),
    "jw_agent_toolkit.embedders": ("name", "target", "dim", "is_available", "embed"),
    "jw_agent_toolkit.vlm_providers": ("name", "is_available", "describe"),
    "jw_agent_toolkit.gen_providers": ("name", "is_available", "generate"),
}

OPTIONAL_BY_GROUP: dict[str, tuple[str, ...]] = {
    "jw_agent_toolkit.agents": ("languages", "version", "cost_estimate"),
    "jw_agent_toolkit.parsers": ("extensions", "mime_types"),
    "jw_agent_toolkit.embedders": ("max_tokens",),
    "jw_agent_toolkit.vlm_providers": ("languages",),
    "jw_agent_toolkit.gen_providers": ("max_tokens", "supports_streaming"),
}


def _plugin_dependencies(spec: EntryPointSpec) -> tuple[str, ...]:
    try:
        dist = distribution(spec.dist_name)
    except Exception:  # noqa: BLE001
        return ()
    return tuple(dist.requires or ())


def _check_version_constraint(
    requirements: tuple[str, ...],
    installed_version: str,
) -> tuple[str | None, bool]:
    for raw in requirements:
        try:
            req = Requirement(raw)
        except Exception:  # noqa: BLE001
            continue
        if req.name.lower().replace("_", "-") != "jw-agent-toolkit":
            continue
        if req.specifier and not req.specifier.contains(
            Version(installed_version), prereleases=True
        ):
            return raw, False
        return raw, True
    return None, True


def _verify_spec(
    spec: EntryPointSpec,
    *,
    target: Any,
    plugin_dependencies: tuple[str, ...] | None = None,
) -> VerifyReport:
    required = REQUIRED_BY_GROUP.get(spec.group, ())
    optional = OPTIONAL_BY_GROUP.get(spec.group, ())

    req_present = tuple(a for a in required if hasattr(target, a))
    req_missing = tuple(a for a in required if not hasattr(target, a))
    opt_present = tuple(a for a in optional if hasattr(target, a))
    opt_missing = tuple(a for a in optional if not hasattr(target, a))

    deps = plugin_dependencies if plugin_dependencies is not None else _plugin_dependencies(spec)
    installed = jw_core.__version__
    constraint, satisfied = _check_version_constraint(deps, installed)

    ok = not req_missing and satisfied

    return VerifyReport(
        name=spec.name,
        group=spec.group,
        dist_name=spec.dist_name,
        dist_version=spec.dist_version,
        ok=ok,
        required_present=req_present,
        required_missing=req_missing,
        optional_present=opt_present,
        optional_missing=opt_missing,
        version_constraint=constraint,
        version_satisfied=satisfied,
        errors=(),
    )


def _resolve_spec(name: str, group: str) -> tuple[EntryPointSpec, Any]:
    plugins = get_plugins(group)
    spec = plugins.get(name)
    if spec is None:
        for v in plugins.values():
            if v.namespaced_name == name:
                spec = v
                break
    if spec is None:
        raise PluginError(f"plugin {name!r} not found in group {group!r}")
    return spec, spec.resolve()


def verify_plugin(name: str, group: str) -> VerifyReport:
    """Verify a discovered plugin. Strict mode raises; soft mode returns report."""

    spec, target = _resolve_spec(name, group)
    report = _verify_spec(spec, target=target)

    strict = os.getenv(ENV_STRICT, "").strip() == "1"

    if not report.version_satisfied:
        if strict:
            raise PluginVersionMismatch(
                plugin_name=name,
                constraint=report.version_constraint or "<unknown>",
                installed_version=jw_core.__version__,
            )
        logger.warning(
            "plugin %r requires %r but installed %r — skipping",
            name,
            report.version_constraint,
            jw_core.__version__,
        )

    if report.required_missing:
        if strict:
            raise PluginContractError(
                plugin_name=name,
                group=group,
                missing=list(report.required_missing),
            )
        logger.warning(
            "plugin %r in group %r missing required attrs: %s",
            name,
            group,
            list(report.required_missing),
        )

    return report
