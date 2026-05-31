"""Smoke tests for the Textual app builders (only run if textual installed)."""

from __future__ import annotations

from pathlib import Path

import pytest


def _has_textual() -> bool:
    try:
        import textual  # noqa: F401

        return True
    except ImportError:
        return False


pytestmark = pytest.mark.skipif(not _has_textual(), reason="textual not installed")


def test_build_wizard_app_returns_app_instance() -> None:
    from jw_finetune.tui.app import build_wizard_app

    app = build_wizard_app()
    assert app is not None
    # The wizard state should be initialized
    assert hasattr(app, "state")
    assert app.state.step == "choose_preset"


def test_build_monitor_app_returns_app_instance(tmp_path: Path) -> None:
    from jw_finetune.tui.app import build_monitor_app

    events = tmp_path / "events.jsonl"
    events.write_text("", encoding="utf-8")
    app = build_monitor_app(events)
    assert app is not None
    assert app.events_path == events
