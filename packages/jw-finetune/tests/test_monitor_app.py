"""Tests for the FastAPI monitor app routes."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest


def _has_fastapi() -> bool:
    try:
        import fastapi  # noqa: F401
        return True
    except ImportError:
        return False


pytestmark = pytest.mark.skipif(not _has_fastapi(), reason="fastapi not installed")


def test_create_app_returns_fastapi_instance(tmp_path: Path) -> None:
    from jw_finetune.monitor.app import create_app
    app = create_app(tmp_path / "events.jsonl")
    # Smoke: the app has the routes we care about
    paths = {r.path for r in app.routes if hasattr(r, "path")}
    assert "/" in paths
    assert "/api/metrics" in paths
    assert "/api/events" in paths


def test_index_returns_html(tmp_path: Path) -> None:
    from fastapi.testclient import TestClient

    from jw_finetune.monitor.app import create_app

    events = tmp_path / "events.jsonl"
    events.write_text("", encoding="utf-8")
    app = create_app(events)
    client = TestClient(app)
    r = client.get("/")
    assert r.status_code == 200
    assert "<!DOCTYPE html>" in r.text
    assert "jw-finetune monitor" in r.text


def test_api_metrics_returns_json(tmp_path: Path) -> None:
    from fastapi.testclient import TestClient

    from jw_finetune.monitor.app import create_app

    app = create_app(tmp_path / "events.jsonl")
    client = TestClient(app)
    r = client.get("/api/metrics")
    assert r.status_code == 200
    body = r.json()
    assert "cpu_percent" in body
    assert "gpu_kind" in body


def test_api_events_returns_buffer(tmp_path: Path) -> None:
    from fastapi.testclient import TestClient

    from jw_finetune.monitor.app import create_app

    events = tmp_path / "events.jsonl"
    events.write_text(
        json.dumps({"kind": "step", "loss": 0.7}) + "\n",
        encoding="utf-8",
    )
    app = create_app(events)
    with TestClient(app) as client:
        # Give the lifespan tail loop a moment
        import time
        time.sleep(0.8)
        r = client.get("/api/events?limit=10")
        assert r.status_code == 200
        body = r.json()
        assert "events" in body
        assert body["count"] >= 1
