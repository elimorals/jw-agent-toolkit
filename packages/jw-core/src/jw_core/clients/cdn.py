"""Client for b.jw-cdn.org — search + JWT auth.

The jw.org public site uses an undocumented JSON search API hosted on a CDN
subdomain (`b.jw-cdn.org`). The flow is:

  1. Fetch a short-lived JWT from `b.jw-cdn.org/tokens/jworg.jwt`
     (handled by `jw_core.auth.JWTManager`).
  2. Send authenticated GET to `b.jw-cdn.org/apis/search/results/{lang}/{filter}?q=...`.
  3. The response is JSON with results (grouped or flat depending on filter).

Optional Phase 9 wire-up: pass `throttler`, `cache`, and/or `telemetry`
to throttle requests per host, cache responses on disk, and record API
shape drift respectively.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from jw_core.auth import JWTManager
from jw_core.cache import DiskCache
from jw_core.clients._polite import politely_get
from jw_core.telemetry import Telemetry
from jw_core.throttle import Throttler

logger = logging.getLogger(__name__)

SEARCH_BASE = "https://b.jw-cdn.org/apis/search/results"

VALID_FILTERS = {"all", "publications", "videos", "audio", "bible", "indexes"}


class CDNError(RuntimeError):
    """Raised when the CDN returns an unrecoverable error."""


class CDNClient:
    """Async client for the b.jw-cdn.org search API."""

    def __init__(
        self,
        http: httpx.AsyncClient | None = None,
        *,
        throttler: Throttler | None = None,
        cache: DiskCache | None = None,
        telemetry: Telemetry | None = None,
        auth: JWTManager | None = None,
    ) -> None:
        self._http = http or httpx.AsyncClient(timeout=30.0, follow_redirects=True)
        self._owns_http = http is None
        self._throttler = throttler
        self._cache = cache
        self._telemetry = telemetry
        self._auth = auth or JWTManager(self._http)

    async def search(
        self,
        query: str,
        *,
        filter_type: str = "all",
        language: str = "E",
        limit: int = 10,
    ) -> dict[str, Any]:
        """Search jw.org. Returns the raw JSON response."""
        if filter_type not in VALID_FILTERS:
            raise ValueError(
                f"filter_type must be one of {sorted(VALID_FILTERS)}, got {filter_type!r}"
            )
        url = f"{SEARCH_BASE}/{language}/{filter_type}"
        headers = await self._auth.authorized_headers()
        try:
            resp = await politely_get(
                self._http, url, params={"q": query}, headers=headers,
                throttler=self._throttler, cache=self._cache, telemetry=self._telemetry,
                endpoint_id="cdn.search", record_json_shape=True,
                cache_ttl_seconds=900.0,  # 15 minutes — same as jw-org-mcp
            )
            if resp.status_code == 401:
                # Token expired — refresh once and retry.
                self._auth.invalidate()
                headers = await self._auth.authorized_headers(force_refresh=True)
                resp = await politely_get(
                    self._http, url, params={"q": query}, headers=headers,
                    throttler=self._throttler, cache=self._cache, telemetry=self._telemetry,
                    endpoint_id="cdn.search", record_json_shape=True,
                )
            resp.raise_for_status()
        except httpx.HTTPError as e:
            raise CDNError(f"Search request failed: {e}") from e

        data = resp.json()
        return self._truncate(data, limit)

    @staticmethod
    def _truncate(data: dict[str, Any], limit: int) -> dict[str, Any]:
        if limit <= 0:
            return data
        if "results" in data and isinstance(data["results"], list):
            data = {**data, "results": data["results"][:limit]}
        return data

    def cache_stats(self) -> dict[str, int] | None:
        """Return DiskCache stats if a cache is configured, else None."""
        return self._cache.stats() if self._cache is not None else None

    async def aclose(self) -> None:
        if self._owns_http:
            await self._http.aclose()
