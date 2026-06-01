"""jw_core.plugins — entry-point discovery for community extensions.

Public API:
    from jw_core.plugins import (
        get_plugins,
        clear_plugin_cache,
        verify_plugin,
        PluginError,
        PluginConflictError,
        PluginContractError,
        PluginVersionMismatch,
    )

Five extension-point groups (PEP 621 entry points):
    jw_agent_toolkit.agents
    jw_agent_toolkit.parsers
    jw_agent_toolkit.embedders
    jw_agent_toolkit.vlm_providers
    jw_agent_toolkit.gen_providers
"""

from __future__ import annotations

from jw_core.plugins.errors import (
    PluginConflictError,
    PluginContractError,
    PluginError,
    PluginVersionMismatch,
)
from jw_core.plugins.factory import clear_plugin_cache, get_plugins
from jw_core.plugins.verify import verify_plugin

__all__ = [
    "PluginConflictError",
    "PluginContractError",
    "PluginError",
    "PluginVersionMismatch",
    "clear_plugin_cache",
    "get_plugins",
    "verify_plugin",
]
