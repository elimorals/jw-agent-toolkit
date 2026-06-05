"""Verify CORS is tightened to the wol.jw.org + extension origins.

Replaces the previous ``allow_origins=["*"]`` permissive default. Required
by Fase 48 (WOL browser extension) to enforce that only the surfaces we
own can call the local REST API.
"""

from __future__ import annotations

from fastapi.testclient import TestClient
from jw_mcp.rest_api import app


def _client() -> TestClient:
    return TestClient(app)


def test_cors_allows_wol() -> None:
    r = _client().get(
        "/healthz",
        headers={
            "Origin": "https://wol.jw.org",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert r.headers.get("access-control-allow-origin") == "https://wol.jw.org"


def test_cors_allows_chrome_extension() -> None:
    origin = "chrome-extension://abcdefghijklmnopabcdefghijklmnop"
    r = _client().get("/healthz", headers={"Origin": origin})
    assert r.headers.get("access-control-allow-origin") == origin


def test_cors_allows_moz_extension() -> None:
    origin = "moz-extension://11111111-2222-3333-4444-555555555555"
    r = _client().get("/healthz", headers={"Origin": origin})
    assert r.headers.get("access-control-allow-origin") == origin


def test_cors_blocks_random_https_origin() -> None:
    r = _client().get(
        "/healthz", headers={"Origin": "https://attacker.example.com"}
    )
    # FastAPI's CORSMiddleware in regex mode omits the header for non-matches.
    assert r.headers.get("access-control-allow-origin") in (None, "")


def test_cors_blocks_http_localhost_from_wrong_port() -> None:
    r = _client().get("/healthz", headers={"Origin": "http://localhost:9999"})
    assert r.headers.get("access-control-allow-origin") in (None, "")


def test_cors_preflight_options() -> None:
    r = _client().options(
        "/api/v1/verse_markdown",
        headers={
            "Origin": "https://wol.jw.org",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    assert r.status_code in (200, 204)
    assert r.headers.get("access-control-allow-origin") == "https://wol.jw.org"
    assert "POST" in (r.headers.get("access-control-allow-methods") or "")
