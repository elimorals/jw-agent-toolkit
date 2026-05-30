"""Tests for the politely_get HTTP helper — throttle + cache + telemetry."""

import asyncio
from pathlib import Path

import httpx
from jw_core.cache import DiskCache
from jw_core.clients._polite import _cache_key, politely_get
from jw_core.telemetry import Telemetry
from jw_core.throttle import Throttler


def _mock_transport(status: int = 200, body: bytes = b'{"ok": true}') -> httpx.MockTransport:
    """Build a MockTransport that always responds with the given body."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            status,
            content=body,
            headers={"content-type": "application/json"},
        )

    return httpx.MockTransport(handler)


def _client(status: int = 200, body: bytes = b'{"ok": true}') -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=_mock_transport(status, body))


# ── Cache integration ──────────────────────────────────────────────────


def test_cache_key_deterministic_for_same_params() -> None:
    a = _cache_key("https://x.com/a", {"q": "love", "lang": "E"})
    b = _cache_key("https://x.com/a", {"lang": "E", "q": "love"})
    assert a == b


def test_cache_key_different_params_give_different_keys() -> None:
    a = _cache_key("https://x.com/a", {"q": "love"})
    b = _cache_key("https://x.com/a", {"q": "peace"})
    assert a != b


def test_polite_get_caches_response_body(tmp_path: Path) -> None:
    async def run() -> None:
        cache = DiskCache(tmp_path / "c.db")
        try:
            async with _client(body=b'{"first": true}') as http:
                r1 = await politely_get(http, "https://api.test/x", cache=cache)
                assert r1.json() == {"first": True}
            # New client (new mock) — but cache should serve from disk now.
            async with _client(body=b'{"second": true}') as http:
                r2 = await politely_get(http, "https://api.test/x", cache=cache)
                # Served from cache → still the first body.
                assert r2.json() == {"first": True}
        finally:
            cache.close()

    asyncio.run(run())


def test_polite_get_without_cache_always_fetches() -> None:
    async def run() -> None:
        async with _client(body=b'{"v": 1}') as http:
            r = await politely_get(http, "https://api.test/x")
            assert r.json() == {"v": 1}

    asyncio.run(run())


# ── Throttler integration ─────────────────────────────────────────────


def test_polite_get_consumes_a_throttle_token() -> None:
    async def run() -> None:
        throttler = Throttler(default_rate=100.0, default_capacity=2.0)
        async with _client() as http:
            await politely_get(http, "https://api.test/x", throttler=throttler)
            # After 1 acquire, bucket has 1 token left.
            bucket = throttler.bucket_for("api.test")
            assert 0.5 < bucket._tokens < 2.0

    asyncio.run(run())


# ── Telemetry integration ─────────────────────────────────────────────


def test_polite_get_records_telemetry_shape(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("JW_TELEMETRY_ENABLED", "1")

    async def run() -> None:
        tel = Telemetry(tmp_path / "tel.json")
        async with _client(body=b'{"a": 1, "b": "x"}') as http:
            await politely_get(
                http,
                "https://api.test/x",
                telemetry=tel,
                endpoint_id="test.endpoint",
                record_json_shape=True,
            )
            assert "test.endpoint" in tel.report()["baselines"]

    asyncio.run(run())


def test_polite_get_telemetry_detects_drift(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("JW_TELEMETRY_ENABLED", "1")

    async def run() -> None:
        tel = Telemetry(tmp_path / "tel.json")
        async with _client(body=b'{"a": 1}') as http:
            await politely_get(
                http,
                "https://api.test/x",
                telemetry=tel,
                endpoint_id="endpoint.drift",
                record_json_shape=True,
            )
        async with _client(body=b'{"a": 1, "newKey": []}') as http:
            await politely_get(
                http,
                "https://api.test/y",  # different URL same endpoint id
                telemetry=tel,
                endpoint_id="endpoint.drift",
                record_json_shape=True,
            )
        assert tel.report()["drift_events"]

    asyncio.run(run())


# ── Clients accept Phase 9 deps without breaking ──────────────────────


def test_cdn_client_accepts_phase9_deps(tmp_path: Path) -> None:
    """Smoke check: CDNClient can be constructed with all Phase 9 wiring."""
    from jw_core.clients.cdn import CDNClient

    throttler = Throttler()
    cache = DiskCache(tmp_path / "c.db")
    tel = Telemetry()
    client = CDNClient(throttler=throttler, cache=cache, telemetry=tel)
    assert client.cache_stats() == cache.stats()
    cache.close()


def test_wol_client_accepts_phase9_deps(tmp_path: Path) -> None:
    from jw_core.clients.wol import WOLClient

    cache = DiskCache(tmp_path / "c.db")
    client = WOLClient(cache=cache)
    assert client.cache_stats() == cache.stats()
    cache.close()


def test_factory_builds_complete_suite(tmp_path: Path) -> None:
    from jw_core.clients.factory import build_clients

    suite = build_clients(tmp_path / "c.db")
    assert suite.cdn is not None
    assert suite.wol is not None
    assert suite.mediator is not None
    assert suite.pub_media is not None
    assert suite.topic_index is not None
    assert suite.weblang is not None
    assert suite.throttler is not None
    assert suite.cache is not None
    asyncio.run(suite.aclose())
