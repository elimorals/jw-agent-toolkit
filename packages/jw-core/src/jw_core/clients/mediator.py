"""Client for data.jw-api.org/mediator/* — language registry + content finder.

Two endpoints wrapped here:

  GET /mediator/v1/languages/{lang}                  → list of languages with metadata
  GET /mediator/finder?lang=X&item=Y                 → resolve a content code to real URLs

Used to build language tables (with ISO codes, names, RTL flag, sign-language
flag) and to map content keys (like 'pub-edj_x_VIDEO') to deliverable URLs.

These endpoints are public, unauthenticated, and well-cached on the CDN.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx
from pydantic import BaseModel, Field

from jw_core.cache import DiskCache
from jw_core.clients._polite import politely_get
from jw_core.telemetry import Telemetry
from jw_core.throttle import Throttler

logger = logging.getLogger(__name__)

MEDIATOR_BASE = "https://data.jw-api.org/mediator"


class MediatorError(RuntimeError):
    pass


class MediatorLanguage(BaseModel):
    """A language entry as returned by /mediator/v1/languages/{lang}.

    Fields are conservatively-typed because the API returns extra keys we
    don't all need; unknown keys are ignored.
    """

    code: str = Field(description="JW internal code, e.g. 'E', 'S'")
    locale: str = Field(default="", description="ISO 639-1 lowercase")
    name: str = Field(default="", description="Display name in the request language")
    vernacular: str = Field(default="", description="Display name in the language itself")
    rtl: bool = Field(default=False, description="Right-to-left script")
    is_sign_language: bool = Field(default=False)
    has_web_content: bool = Field(default=True)

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> MediatorLanguage:
        return cls(
            code=data.get("symbol", data.get("code", "")),
            locale=data.get("locale", ""),
            name=data.get("name", ""),
            vernacular=data.get("vernacularName", ""),
            rtl=data.get("direction", "") == "rtl",
            is_sign_language=bool(data.get("isSignLanguage", False)),
            has_web_content=bool(data.get("hasWebContent", True)),
        )


class MediatorClient:
    """Async client for data.jw-api.org/mediator."""

    def __init__(
        self,
        http: httpx.AsyncClient | None = None,
        *,
        throttler: Throttler | None = None,
        cache: DiskCache | None = None,
        telemetry: Telemetry | None = None,
    ) -> None:
        self._http = http or httpx.AsyncClient(timeout=30.0, follow_redirects=True)
        self._owns_http = http is None
        self._throttler = throttler
        self._cache = cache
        self._telemetry = telemetry

    async def list_languages(self, in_language: str = "E") -> list[MediatorLanguage]:
        """Fetch the full language registry.

        `in_language` controls the display name language (JW code, e.g. 'E', 'S').
        """
        url = f"{MEDIATOR_BASE}/v1/languages/{in_language}/web"
        try:
            resp = await politely_get(
                self._http,
                url,
                throttler=self._throttler,
                cache=self._cache,
                telemetry=self._telemetry,
                endpoint_id="mediator.list_languages",
                record_json_shape=True,
                cache_ttl_seconds=86400.0,  # languages are stable; cache 1 day
            )
            resp.raise_for_status()
            data = resp.json()
        except httpx.HTTPError as e:
            raise MediatorError(f"list_languages failed: {e}") from e

        # The endpoint returns either {'languages': [...]} or a wrapper depending
        # on the variant. Be flexible.
        items = data.get("languages") or data.get("results") or []
        return [MediatorLanguage.from_api(item) for item in items]

    async def find_item(self, item_code: str, language: str = "E") -> dict[str, Any]:
        """Resolve a content code (e.g. 'pub-edj_x_VIDEO') to its real URL.

        Returns the raw JSON response so callers can inspect every link the
        finder exposes.
        """
        url = f"{MEDIATOR_BASE}/finder"
        try:
            resp = await politely_get(
                self._http,
                url,
                params={"lang": language, "item": item_code},
                throttler=self._throttler,
                cache=self._cache,
                telemetry=self._telemetry,
                endpoint_id="mediator.find_item",
                record_json_shape=True,
            )
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPError as e:
            raise MediatorError(f"find_item({item_code!r}) failed: {e}") from e

    def cache_stats(self) -> dict[str, int] | None:
        return self._cache.stats() if self._cache is not None else None

    async def aclose(self) -> None:
        if self._owns_http:
            await self._http.aclose()
