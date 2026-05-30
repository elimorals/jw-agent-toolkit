"""Tests for the observability module (Module 10)."""

from __future__ import annotations

import io
import json
import logging
import os
from contextlib import redirect_stderr

from jw_core.observability import configure_logging, get_logger, log_event


def test_text_format_default(monkeypatch) -> None:
    monkeypatch.delenv("JW_LOG_FORMAT", raising=False)
    monkeypatch.delenv("JW_LOG_LEVEL", raising=False)
    buf = io.StringIO()
    with redirect_stderr(buf):
        configure_logging(level="INFO", fmt="text")
        get_logger("test").info("hello")
    assert "hello" in buf.getvalue()


def test_json_format_emits_object() -> None:
    buf = io.StringIO()
    with redirect_stderr(buf):
        configure_logging(level="INFO", fmt="json")
        get_logger("jw.test").info("event")
    last = buf.getvalue().strip().splitlines()[-1]
    payload = json.loads(last)
    assert payload["msg"] == "event"
    assert payload["level"] == "INFO"


def test_log_event_attaches_fields() -> None:
    buf = io.StringIO()
    with redirect_stderr(buf):
        configure_logging(level="INFO", fmt="json")
        log_event(get_logger("jw.dispatch"), "request_started", endpoint="/api/v1/verse", duration_ms=42)
    last = buf.getvalue().strip().splitlines()[-1]
    payload = json.loads(last)
    assert payload["endpoint"] == "/api/v1/verse"
    assert payload["duration_ms"] == 42


def test_env_var_overrides() -> None:
    os.environ["JW_LOG_LEVEL"] = "DEBUG"
    os.environ["JW_LOG_FORMAT"] = "text"
    try:
        configure_logging()
        # Root logger should now accept DEBUG.
        assert logging.getLogger().isEnabledFor(logging.DEBUG)
    finally:
        os.environ.pop("JW_LOG_LEVEL", None)
        os.environ.pop("JW_LOG_FORMAT", None)
