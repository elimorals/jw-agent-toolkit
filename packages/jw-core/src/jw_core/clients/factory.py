"""Convenience factory: build a complete client suite with Phase 9 deps wired.

For production use, build all five HTTP clients with one shared `Throttler`,
`DiskCache`, and `Telemetry`. Each client will then automatically:

  - Rate-limit per host (jw.org, jw-cdn.org, jw-api.org).
  - Cache GET responses on disk with sensible per-endpoint TTLs.
  - Record response shape fingerprints to detect API drift.

Usage:

    from jw_core.clients.factory import build_clients
    clients = build_clients()
    await clients.cdn.search("amor")
    await clients.wol.get_today_homepage(language="es")
    ...
    await clients.aclose()

For tests, construct individual clients without these deps (the default).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from jw_core.cache import DiskCache
from jw_core.clients.cdn import CDNClient
from jw_core.clients.mediator import MediatorClient
from jw_core.clients.pub_media import PubMediaClient
from jw_core.clients.topic_index import TopicIndexClient
from jw_core.clients.weblang import WeblangClient
from jw_core.clients.wol import WOLClient
from jw_core.telemetry import Telemetry, get_telemetry
from jw_core.throttle import Throttler


@dataclass
class ClientSuite:
    """Bundle of every HTTP client, sharing the same throttler/cache/telemetry."""

    cdn: CDNClient
    wol: WOLClient
    mediator: MediatorClient
    pub_media: PubMediaClient
    topic_index: TopicIndexClient
    weblang: WeblangClient
    throttler: Throttler
    cache: DiskCache
    # The shared Telemetry instance (or None when telemetry is off). Exposed
    # so downstream callers can wire ad-hoc clients (e.g. JWBroadcasting in
    # news_monitor) into the same drift-detection channel as the suite.
    telemetry: Telemetry | None = None

    async def aclose(self) -> None:
        await self.cdn.aclose()
        await self.wol.aclose()
        await self.mediator.aclose()
        await self.pub_media.aclose()
        await self.topic_index.aclose()
        await self.weblang.aclose()
        self.cache.close()


def build_clients(
    cache_path: Path | str = "~/.jw-agent-toolkit/cache.db",
    *,
    enable_throttling: bool = True,
    enable_cache: bool = True,
    enable_telemetry: bool | None = None,
) -> ClientSuite:
    """Wire a complete suite of jw.org HTTP clients.

    Args:
        cache_path: SQLite path for the response cache.
        enable_throttling: when True, requests pass through a per-host
            token bucket with conservative defaults (2 req/s, burst 5).
        enable_cache: when True, GET responses are cached to disk.
        enable_telemetry: defaults to whatever `Telemetry` reads from
            the `JW_TELEMETRY_ENABLED` env var.
    """
    throttler = Throttler() if enable_throttling else None
    # Tighter limit for the CDN search endpoint (it's the most chatty).
    if throttler is not None:
        throttler.set_limit("b.jw-cdn.org", rate_per_sec=1.0, capacity=3.0)
    cache = DiskCache(cache_path) if enable_cache else None
    telemetry = get_telemetry() if enable_telemetry is None else None

    cdn = CDNClient(throttler=throttler, cache=cache, telemetry=telemetry)
    wol = WOLClient(throttler=throttler, cache=cache, telemetry=telemetry)
    mediator = MediatorClient(throttler=throttler, cache=cache, telemetry=telemetry)
    pub_media = PubMediaClient(throttler=throttler, cache=cache, telemetry=telemetry)
    weblang = WeblangClient(throttler=throttler, cache=cache, telemetry=telemetry)
    topic_index = TopicIndexClient(
        cdn=cdn,
        wol=wol,
        throttler=throttler,
        cache=cache,
        telemetry=telemetry,
    )

    return ClientSuite(
        cdn=cdn,
        wol=wol,
        mediator=mediator,
        pub_media=pub_media,
        topic_index=topic_index,
        weblang=weblang,
        throttler=throttler or Throttler(),  # never None in the bundle for typing
        cache=cache or DiskCache(cache_path),
        telemetry=telemetry,
    )
