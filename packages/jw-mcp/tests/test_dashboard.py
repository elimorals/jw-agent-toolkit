"""Smoke test for the dashboard HTML endpoint."""

from __future__ import annotations

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("starlette")

from fastapi.testclient import TestClient

from jw_mcp.rest_api import app


def test_dashboard_returns_html() -> None:
    client = TestClient(app)
    resp = client.get("/dashboard")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
    body = resp.text
    assert "jw-agent-toolkit" in body
    assert "Profile" in body
    assert "Upcoming events" in body
    assert "TTS engines" in body


def test_healthz_still_works() -> None:
    client = TestClient(app)
    resp = client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
