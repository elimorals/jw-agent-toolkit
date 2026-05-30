"""Shared HTTP helper that wires Throttler + DiskCache + Telemetry into clients.

Every HTTP client in `jw_core.clients.*` accepts optional `throttler`,
`cache`, and `telemetry` instances. When all three are wired (see
`jw_core.clients.factory.build_clients()`), every GET request is:

  1. Rate-limited by per-host token bucket (Throttler).
  2. Cache-checked against a local SQLite TTL store (DiskCache).
  3. Telemetry-tracked for response-shape drift (Telemetry).

When the optional dependencies are None, the helper degrades to a
plain `http.get()`.

The cache key is `f"GET {url}?{sorted_params}"`. The cached value is the
response body bytes; status/headers are not preserved (caller already
expects a 200 if we hit the cache).
"""

from __future__ import annotations

import json
import logging
from typing import Any
from urllib.parse import urlparse

import httpx

from jw_core.cache import DiskCache
from jw_core.telemetry import Telemetry
from jw_core.throttle import Throttler

logger = logging.getLogger(__name__)


async def politely_get(
    http: httpx.AsyncClient,
    url: str,
    *,
    params: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    throttler: Throttler | None = None,
    cache: DiskCache | None = None,
    telemetry: Telemetry | None = None,
    endpoint_id: str | None = None,
    cache_ttl_seconds: float | None = None,
    record_json_shape: bool = False,
) -> httpx.Response:
    """GET wrapped with throttling, caching, and telemetry.

    Args:
        http: live httpx client (owned by the caller).
        url: target URL.
        params: query string.
        headers: extra headers.
        throttler: optional Throttler; if set, awaits a token for the URL host.
        cache: optional DiskCache; if set, GETs are cached by (URL, params)
            for `cache_ttl_seconds` (defaults to the cache's default TTL).
        telemetry: optional Telemetry; if set + `record_json_shape=True`,
            JSON responses are fingerprinted under `endpoint_id`.
        endpoint_id: identifier used as the telemetry key (e.g. `"cdn.search"`).
            Defaults to the URL host + path.
        cache_ttl_seconds: per-call cache TTL override.
        record_json_shape: when True, parse the response as JSON and feed
            its shape into `telemetry.record()`.

    Returns:
        An httpx.Response. When served from cache, it's a synthetic Response
        with status 200 and the cached body bytes.
    """
    host = urlparse(url).hostname or url
    cache_key = _cache_key(url, params) if cache is not None else None

    if cache is not None and cache_key is not None:
        hit = cache.get(cache_key)
        if hit is not None:
            logger.debug(f"cache hit: {cache_key}")
            return _synthetic_response(http, url, hit)

    if throttler is not None:
        await throttler.acquire(host)

    resp = await http.get(url, params=params, headers=headers)

    if resp.status_code == 200 and cache is not None and cache_key is not None:
        cache.set(cache_key, resp.content, ttl_seconds=cache_ttl_seconds)

    if (
        telemetry is not None
        and record_json_shape
        and resp.status_code == 200
        and "application/json" in resp.headers.get("content-type", "")
    ):
        endpoint = endpoint_id or f"{host}{urlparse(url).path}"
        try:
            telemetry.record(endpoint, resp.json())
        except Exception as e:
            logger.debug(f"telemetry record failed for {endpoint}: {e}")

    return resp


def _cache_key(url: str, params: dict[str, Any] | None) -> str:
    """Build a deterministic cache key for a GET request."""
    if not params:
        return f"GET {url}"
    items = sorted((k, str(v)) for k, v in params.items())
    return f"GET {url}?{json.dumps(items, sort_keys=True)}"


def _synthetic_response(
    http: httpx.AsyncClient, url: str, body: bytes
) -> httpx.Response:
    """Build a 200 response from a cached body so callers see normal API."""
    req = httpx.Request("GET", url)
    return httpx.Response(200, content=body, request=req)
