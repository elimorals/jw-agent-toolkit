"""JWT token lifecycle for the jw-cdn.org search API.

Extracted from `clients/cdn.py` (Phase 9 wire-up). The token is short-lived
(minutes) so we cache it in memory and refresh on demand. Callers receive
a `Bearer ...` header value ready to drop into a request.

The actual endpoint is `b.jw-cdn.org/tokens/jworg.jwt`; it returns the
JWT as a JSON-quoted string (we strip the surrounding quotes).
"""

from __future__ import annotations

import asyncio
import logging

import httpx

logger = logging.getLogger(__name__)

TOKEN_URL = "https://b.jw-cdn.org/tokens/jworg.jwt"


class JWTAuthError(RuntimeError):
    pass


class JWTManager:
    """Async-safe holder of a JWT for the jw-cdn.org APIs."""

    def __init__(self, http: httpx.AsyncClient, token_url: str = TOKEN_URL) -> None:
        self._http = http
        self._token_url = token_url
        self._token: str | None = None
        self._lock = asyncio.Lock()

    async def get_token(self, *, force_refresh: bool = False) -> str:
        """Return a cached JWT, fetching it if missing or `force_refresh`."""
        if self._token and not force_refresh:
            return self._token
        async with self._lock:
            # Double-check inside the lock so we don't race two refreshes.
            if self._token and not force_refresh:
                return self._token
            try:
                resp = await self._http.get(self._token_url)
                resp.raise_for_status()
            except httpx.HTTPError as e:
                raise JWTAuthError(f"Token fetch failed: {e}") from e
            self._token = resp.text.strip().strip('"')
            return self._token

    async def authorized_headers(
        self,
        extra: dict[str, str] | None = None,
        *,
        force_refresh: bool = False,
    ) -> dict[str, str]:
        """Build the Authorization-bearing header dict for an API request."""
        token = await self.get_token(force_refresh=force_refresh)
        headers: dict[str, str] = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json; charset=utf-8",
            "Referer": "https://www.jw.org/",
        }
        if extra:
            headers.update(extra)
        return headers

    def invalidate(self) -> None:
        """Drop the cached token (used after a 401 response)."""
        self._token = None
