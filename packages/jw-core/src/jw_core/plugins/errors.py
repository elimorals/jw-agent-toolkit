"""Exception hierarchy for the plugin SDK."""

from __future__ import annotations


class PluginError(Exception):
    """Base for every plugin-SDK error."""


class PluginConflictError(PluginError):
    """Two plugins registered the same name and the conflict policy is REJECT."""

    def __init__(
        self,
        name: str,
        group: str,
        dist_names: tuple[str, ...],
        policy: str,
    ) -> None:
        self.name = name
        self.group = group
        self.dist_names = dist_names
        self.policy = policy
        super().__init__(
            f"plugin name conflict: {name!r} in group {group!r} "
            f"claimed by distributions {list(dist_names)} (policy={policy})"
        )


class PluginVersionMismatch(PluginError):
    """A plugin declares a jw-agent-toolkit constraint that the current install violates."""

    def __init__(
        self,
        plugin_name: str,
        constraint: str,
        installed_version: str,
    ) -> None:
        self.plugin_name = plugin_name
        self.constraint = constraint
        self.installed_version = installed_version
        super().__init__(
            f"plugin {plugin_name!r} requires {constraint!r} "
            f"but installed jw-agent-toolkit version is {installed_version!r}"
        )


class PluginContractError(PluginError):
    """A plugin fails the Protocol contract for its group."""

    def __init__(
        self,
        plugin_name: str,
        group: str,
        missing: list[str],
        extra: dict[str, str] | None = None,
    ) -> None:
        self.plugin_name = plugin_name
        self.group = group
        self.missing = list(missing)
        self.extra = dict(extra or {})
        joined = ", ".join(missing) or "<none>"
        super().__init__(
            f"plugin {plugin_name!r} in group {group!r} missing required: [{joined}]"
        )
