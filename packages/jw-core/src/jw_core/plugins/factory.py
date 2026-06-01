"""Public facade: cached `get_plugins(group)` + `clear_plugin_cache`."""

from __future__ import annotations

from functools import lru_cache

from jw_core.plugins.contracts import EntryPointSpec
from jw_core.plugins.errors import PluginError
from jw_core.plugins.registry import GROUPS, _discover


@lru_cache(maxsize=None)
def _cached_discover(group: str) -> tuple[tuple[str, EntryPointSpec], ...]:
    """Internal cached layer. Returns sorted-tuple form so `lru_cache` is happy."""

    if group not in GROUPS:
        raise PluginError(
            f"unknown plugin group {group!r}; expected one of {list(GROUPS)}"
        )
    discovered = _discover(group)
    return tuple(sorted(discovered.items()))


def get_plugins(group: str) -> dict[str, EntryPointSpec]:
    """Return all plugins for `group`, post-policy + post-filter. Cached per process."""

    return dict(_cached_discover(group))


def clear_plugin_cache() -> None:
    """Reset the discovery cache. Useful in tests; idempotent."""

    _cached_discover.cache_clear()
