"""Tests for POST /api/v1/cross_references — used by the WOL extension.

Network resilience: the endpoint dispatches to the CDN search. In CI without
internet we still expect a 200 response with a stable shape (empty refs +
optional error string). The endpoint must never 5xx for shape errors.
"""

from __future__ import annotations

from fastapi.testclient import TestClient
from jw_mcp.rest_api import app


def test_cross_references_returns_list() -> None:
    c = TestClient(app)
    r = c.post(
        "/api/v1/cross_references",
        json={"reference": "Juan 3:16", "language": "es"},
    )
    assert r.status_code == 200
    body = r.json()
    assert "refs" in body
    assert isinstance(body["refs"], list)


def test_cross_references_rejects_bad_reference() -> None:
    c = TestClient(app)
    r = c.post(
        "/api/v1/cross_references",
        json={"reference": "not a reference", "language": "es"},
    )
    assert r.status_code == 200
    body = r.json()
    # Either explicit error string or empty refs (when CDN is offline)
    assert body.get("error") or body.get("refs") == []


def test_cross_references_each_entry_has_url_and_verse() -> None:
    c = TestClient(app)
    r = c.post(
        "/api/v1/cross_references",
        json={"reference": "John 3:16", "language": "en"},
    )
    assert r.status_code == 200
    body = r.json()
    for ref in body.get("refs", []):
        assert "verse" in ref
        assert "url" in ref
        assert ref["url"].startswith("https://wol.jw.org/")
