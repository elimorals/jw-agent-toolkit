"""Client for wol.jw.org — Watchtower ONLINE Library HTML.

Wraps every WOL URL pattern we care about. Most endpoints serve
server-rendered HTML, so this client returns raw HTML and delegates
parsing to `jw_core.parsers.*`.

URL patterns observed:
  - Bible chapter:  /{iso}/wol/b/{r}/{lp_tag}/{pub}/{book_num}/{chapter}
  - Article:        /{iso}/wol/d/{r}/{lp_tag}/{docId}
  - Daily-text doc: /{iso}/wol/d/{r}/{lp_tag}/{docId}      ← per-year docId
  - Daily-text date:/{iso}/wol/dt/{r}/{lp_tag}/{YYYY}/{M}/{D}
  - Today's view:   /{iso}/wol/h/{r}/{lp_tag}
  - Publication:    /{iso}/wol/publication/{r}/{lp_tag}/{pub}[/{num}]
  - Cross-ref panel:/{iso}/wol/bc/{r}/{lp_tag}/{doc}/{group}/{index}

Optional Phase 9 wire-up: pass `throttler`, `cache`, `telemetry`.
"""

from __future__ import annotations

import datetime as _dt
import logging

import httpx

from jw_core.cache import DiskCache
from jw_core.clients._polite import politely_get
from jw_core.languages import get_language
from jw_core.telemetry import Telemetry
from jw_core.throttle import Throttler

logger = logging.getLogger(__name__)

WOL_BASE = "https://wol.jw.org"
USER_AGENT = "jw-agent-toolkit/0.1 (+research)"


class WOLError(RuntimeError):
    pass


class WOLClient:
    """Async client for wol.jw.org HTML pages."""

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
            headers={"User-Agent": USER_AGENT, "Accept-Language": "en,es;q=0.9"},
        )
        self._owns_http = http is None
        self._throttler = throttler
        self._cache = cache
        self._telemetry = telemetry

    async def fetch(self, url: str, *, cache_ttl_seconds: float = 3600.0) -> str:
        """Fetch arbitrary wol.jw.org URL, return HTML text."""
        if not url.startswith("http"):
            url = f"{WOL_BASE}{url}"
        try:
            resp = await politely_get(
                self._http,
                url,
                throttler=self._throttler,
                cache=self._cache,
                telemetry=self._telemetry,
                endpoint_id="wol.fetch",
                cache_ttl_seconds=cache_ttl_seconds,
            )
            resp.raise_for_status()
        except httpx.HTTPError as e:
            raise WOLError(f"Fetch failed for {url}: {e}") from e
        return resp.text

    async def get_bible_chapter(
        self,
        book_num: int,
        chapter: int,
        *,
        language: str = "en",
        publication: str | None = None,
    ) -> tuple[str, str]:
        """Fetch the HTML for a Bible chapter. Returns (url, html).

        `publication` defaults to the language's preferred Bible
        (nwtsty for English, nwt for Spanish/Portuguese).
        """
        lang = get_language(language)
        pub = publication or lang.default_bible
        url = f"{WOL_BASE}/{lang.iso}/wol/b/{lang.wol_resource}/{lang.lp_tag}/{pub}/{book_num}/{chapter}"
        return url, await self.fetch(url)

    async def get_today_homepage(self, language: str = "en") -> tuple[str, str]:
        """Fetch the WOL 'today' homepage which contains today's daily text."""
        lang = get_language(language)
        url = f"{WOL_BASE}/{lang.iso}/wol/h/{lang.wol_resource}/{lang.lp_tag}"
        return url, await self.fetch(url)

    async def get_daily_text_by_date(
        self,
        date: str | _dt.date,
        *,
        language: str = "en",
    ) -> tuple[str, str]:
        """Fetch the daily text for a specific date.

        Uses WOL's date-based pattern `/dt/{r}/{lp_tag}/{YYYY}/{M}/{D}`
        which falls back to the year's daily-text document. Returns
        (url, html).

        Args:
            date: ISO `YYYY-MM-DD` string or a `datetime.date`.
            language: ISO code (en/es/pt).
        """
        if isinstance(date, str):
            date = _dt.date.fromisoformat(date)
        lang = get_language(language)
        url = f"{WOL_BASE}/{lang.iso}/wol/dt/{lang.wol_resource}/{lang.lp_tag}/{date.year}/{date.month}/{date.day}"
        return url, await self.fetch(url)

    async def get_document_by_id(self, doc_id: int | str, *, language: str = "en") -> tuple[str, str]:
        """Fetch a WOL document by its docId (e.g. a daily-text book, article).

        URL: /{iso}/wol/d/{r}/{lp_tag}/{docId}.
        """
        lang = get_language(language)
        url = f"{WOL_BASE}/{lang.iso}/wol/d/{lang.wol_resource}/{lang.lp_tag}/{doc_id}"
        return url, await self.fetch(url)

    async def get_publication_page(
        self,
        pub_code: str,
        number: int | None = None,
        *,
        language: str = "en",
    ) -> tuple[str, str]:
        """Fetch the WOL publication landing / number page.

        URL: /{iso}/wol/publication/{r}/{lp_tag}/{pub}[/{number}].
        For Bible editions (`pub="nwtsty"`), `number=N` opens book N's TOC.
        For magazines, `number` is the issue index. For books, `number` is
        the chapter or section number.

        Returns (url, html). Pair with `parse_article` for clean text.
        """
        lang = get_language(language)
        url = f"{WOL_BASE}/{lang.iso}/wol/publication/{lang.wol_resource}/{lang.lp_tag}/{pub_code}"
        if number is not None:
            url += f"/{number}"
        return url, await self.fetch(url)

    async def get_cross_reference_panel(self, href: str) -> tuple[str, str]:
        """Fetch the cross-reference panel pointed to by an inline marker.

        `href` is the relative path captured from a CrossReference (e.g.
        `/en/wol/bc/r1/lp-e/{doc_id}/{group}/{index}`). Returns (full_url, html).
        """
        if not href.startswith("http"):
            href = f"{WOL_BASE}{href}"
        return href, await self.fetch(href)

    def cache_stats(self) -> dict[str, int] | None:
        return self._cache.stats() if self._cache is not None else None

    async def aclose(self) -> None:
        if self._owns_http:
            await self._http.aclose()
