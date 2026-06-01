"""Smoke: package imports cleanly without optional deps."""

from __future__ import annotations


def test_package_imports() -> None:
    import jw_brain

    assert jw_brain.__version__ == "0.1.0"
