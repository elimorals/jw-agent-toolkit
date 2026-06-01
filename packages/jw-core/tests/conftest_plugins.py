"""Shared fixtures for plugin tests."""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _clear_plugin_cache() -> None:
    from jw_core.plugins import clear_plugin_cache

    clear_plugin_cache()
    yield
    clear_plugin_cache()
