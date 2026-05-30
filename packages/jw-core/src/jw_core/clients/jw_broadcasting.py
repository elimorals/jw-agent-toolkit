"""JW Broadcasting (tv.jw.org) client — discover videos + download subtitles.

LIVE-VERIFIED endpoints (May 2026):

    GET https://data.jw-api.org/mediator/v1/categories/{lang}/{key}?detailed=1
        → {"category": {"subcategories": [...], "media": [...]}}

For each media item we surface `files[0].subtitles.url`, which is the
WebVTT track that feeds `BroadcastingIndex.parse_vtt`.

The mediator API takes JW language codes (E/S/T/F/...). We map ISO via
`jw_core.languages.get_language`.

Category tree (top level VideoOnDemand → subcategories):
    VODStudio          — JW Broadcasting studio shows
    VODChildren        — Children content (Become Jehovah's Friend, songs)
    VODTeenagers       — Teen content
    VODFamily          — Family worship
    VODProgramsEvents  — Annual program, special events
    VODOurActivities   — Field ministry, public meetings, etc.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx

from jw_core.cache import DiskCache
from jw_core.clients._polite import politely_get
from jw_core.languages import get_language
from jw_core.telemetry import Telemetry
from jw_core.throttle import Throttler

logger = logging.getLogger(__name__)

MEDIATOR_BASE = "https://data.jw-api.org/mediator/v1/categories"
DEFAULT_TOP_CATEGORY = "VideoOnDemand"


class BroadcastingError(RuntimeError):
    pass


@dataclass
class BroadcastingVideo:
    guid: str
    natural_key: str
    title: str
    duration_seconds: float = 0.0
    first_published: str = ""
    description: str = ""
    subtitle_url: str = ""
    download_url: str = ""
    tags: list[str] = field(default_factory=list)


@dataclass
class BroadcastingCategory:
    key: str
    name: str
    subcategories: list[str] = field(default_factory=list)
    videos: list[BroadcastingVideo] = field(default_factory=list)


class JWBroadcastingClient:
    """Discover videos and download their subtitle tracks."""

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
            headers={"User-Agent": "jw-agent-toolkit/0.1 (+research)"},
        )
        self._owns_http = http is None
        self._throttler = throttler
        self._cache = cache
        self._telemetry = telemetry

    async def get_category(
        self,
        category_key: str = DEFAULT_TOP_CATEGORY,
        *,
        language: str = "en",
    ) -> BroadcastingCategory:
        lang = get_language(language)
        url = f"{MEDIATOR_BASE}/{lang.jw_code}/{category_key}"
        try:
            resp = await politely_get(
                self._http,
                url,
                params={"detailed": 1},
                throttler=self._throttler,
                cache=self._cache,
                telemetry=self._telemetry,
                endpoint_id="jw_broadcasting.category",
                cache_ttl_seconds=3600.0,
            )
            resp.raise_for_status()
        except httpx.HTTPError as e:
            raise BroadcastingError(f"Category fetch failed: {e}") from e
        data = resp.json().get("category", {}) or {}
        subcats = [sc.get("key", "") for sc in data.get("subcategories", []) if sc.get("key")]
        videos = [self._normalize_video(m) for m in data.get("media", [])]
        return BroadcastingCategory(
            key=data.get("key", category_key),
            name=data.get("name", category_key),
            subcategories=subcats,
            videos=[v for v in videos if v.guid],
        )

    async def discover_all_videos(
        self,
        *,
        language: str = "en",
        root: str = DEFAULT_TOP_CATEGORY,
        max_depth: int = 3,
        limit: int = 200,
    ) -> list[BroadcastingVideo]:
        """Recursively walk the category tree and collect videos."""
        visited: set[str] = set()
        videos: list[BroadcastingVideo] = []

        async def walk(key: str, depth: int) -> None:
            if depth > max_depth or key in visited or len(videos) >= limit:
                return
            visited.add(key)
            try:
                cat = await self.get_category(key, language=language)
            except BroadcastingError as e:
                logger.warning("discover walk failed at %s: %s", key, e)
                return
            videos.extend(cat.videos)
            for child in cat.subcategories:
                if len(videos) >= limit:
                    return
                await walk(child, depth + 1)

        await walk(root, 0)
        return videos[:limit]

    async def download_subtitle(self, video: BroadcastingVideo, dest: Path | str) -> Path:
        if not video.subtitle_url:
            raise BroadcastingError(f"No subtitle URL for {video.guid!r}")
        dest_path = Path(dest)
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            r = await self._http.get(video.subtitle_url)
            r.raise_for_status()
        except httpx.HTTPError as e:
            raise BroadcastingError(f"Subtitle download failed: {e}") from e
        dest_path.write_text(r.text, encoding="utf-8")
        return dest_path

    @staticmethod
    def _normalize_video(item: dict[str, Any]) -> BroadcastingVideo:
        files = item.get("files") or []
        first_file: dict[str, Any] = {}
        if isinstance(files, list) and files:
            # Prefer lowest-resolution that still has a subtitle, else first.
            sorted_files = sorted(
                (f for f in files if isinstance(f, dict)),
                key=lambda f: f.get("frameHeight", 9999),
            )
            for f in sorted_files:
                if (f.get("subtitles") or {}).get("url"):
                    first_file = f
                    break
            if not first_file and sorted_files:
                first_file = sorted_files[0]
        subtitles = first_file.get("subtitles") or {}
        return BroadcastingVideo(
            guid=item.get("guid", ""),
            natural_key=item.get("languageAgnosticNaturalKey", "") or item.get("naturalKey", ""),
            title=item.get("title", ""),
            duration_seconds=float(item.get("duration", 0) or 0),
            first_published=item.get("firstPublished", ""),
            description=item.get("description", "") or "",
            subtitle_url=subtitles.get("url", ""),
            download_url=first_file.get("progressiveDownloadURL", ""),
            tags=item.get("tags", []) or [],
        )

    async def aclose(self) -> None:
        if self._owns_http:
            await self._http.aclose()
