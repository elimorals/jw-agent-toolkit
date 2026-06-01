"""Smoke test: package imports cleanly."""

from __future__ import annotations


def test_package_imports() -> None:
    import create_jw_agent

    assert create_jw_agent.__version__ == "0.1.0"
