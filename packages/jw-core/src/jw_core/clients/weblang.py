"""Client for `www.jw.org/{lang}/languages` — the alternate language registry.

`jwlib.weblang` uses this endpoint and it differs from
`data.jw-api.org/mediator/v1/languages` in subtle but real ways:

- Returns more fields per language (`vernacularName`, `script`, `direction`,
  `isSignLanguage`, alternative spellings).
- Updated less frequently — better for static use cases.
- Available even when the mediator endpoint is throttled.

We keep both clients in the toolkit so callers can pick the right one for
their freshness/throttling profile.
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


class WeblangError(RuntimeError):
    pass


class WeblangLanguage(BaseModel):
    """A language entry as returned by www.jw.org/{lang}/languages."""

    code: str = Field(description="JW internal code, e.g. 'E', 'S'")
    iso: str = Field(default="", description="ISO 639 code (3-letter)")
    name: str = Field(default="", description="Display name (in the requested language)")
    vernacular: str = Field(default="", description="Display name in the language itself")
    alt_names: list[str] = Field(default_factory=list)
    rtl: bool = Field(default=False, description="Right-to-left script")
    script: str = Field(default="", description="e.g. 'ROMAN', 'CYRILLIC'")
    is_sign_language: bool = Field(default=False)

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> WeblangLanguage:
        return cls(
            code=data.get("langcode", data.get("code", "")),
            iso=data.get("symbol", data.get("iso", "")),
            name=data.get("name", ""),
            vernacular=data.get("vernacularName", ""),
            alt_names=data.get("altSpellings", []) or [],
            rtl=data.get("direction", "") == "rtl",
            script=data.get("script", ""),
            is_sign_language=bool(data.get("isSignLanguage", False)),
        )


class WeblangClient:
    """Async client for the public www.jw.org language list."""

    def __init__(
        self,
        http: httpx.AsyncClient | None = None,
        *,
        throttler: Throttler | None = None,
        cache: DiskCache | None = None,
        telemetry: Telemetry | None = None,
    ) -> None:
        self._http = http or httpx.AsyncClient(
            timeout=30.0,
            follow_redirects=True,
            headers={"Accept": "application/json"},
        )
        self._owns_http = http is None
        self._throttler = throttler
        self._cache = cache
        self._telemetry = telemetry

    async def list_languages(self, *, in_language_iso: str = "en") -> list[WeblangLanguage]:
        """Fetch the language list as seen on www.jw.org.

        Args:
            in_language_iso: ISO code for the *display* language (path
                segment of the URL). 'en' returns names in English;
                'es' returns names in Spanish. Defaults to 'en'.
        """
        url = f"https://www.jw.org/{in_language_iso}/languages/"
        try:
            resp = await politely_get(
                self._http,
                url,
                throttler=self._throttler,
                cache=self._cache,
                telemetry=self._telemetry,
                endpoint_id="weblang.list_languages",
                record_json_shape=True,
                cache_ttl_seconds=86400.0,  # languages are stable
            )
            resp.raise_for_status()
            data = resp.json()
        except httpx.HTTPError as e:
            raise WeblangError(f"list_languages failed: {e}") from e
        items = data.get("languages") or []
        return [WeblangLanguage.from_api(item) for item in items]

    def cache_stats(self) -> dict[str, int] | None:
        return self._cache.stats() if self._cache is not None else None

    async def aclose(self) -> None:
        if self._owns_http:
            await self._http.aclose()
