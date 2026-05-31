"""Concrete NewsSource implementations.

A NewsSource is an async object with:
    async def fetch(self, *, languages: list[str], since: datetime | None) -> list[NewsItem]

Three sources ship:

    PublicationsSource — walks `seeds.SEED_PUB_CODES` × `languages` against
                         PubMediaClient.get_publication and emits one NewsItem
                         per file (EPUB/JWPUB/PDF).

    BroadcastingSource — calls JWBroadcastingClient.discover_all_videos and
                         emits one NewsItem per video, keyed by GUID.

    ProgramsSource     — probes the meeting workbook (mwb) and Watchtower
                         study (w) for [now_month, now_month+2) in each
                         language; emits one NewsItem per existing issue,
                         keyed by `mwb{YY}.{MM}` / `w{YY}.{MM}`.

`since` is currently passed through for future filtering. We rely on the
SeenStore for diffing — `since` only constrains *display* of retired items
and the digest header. Sources still report everything they observe; the
caller does the diff.

`languages` are ISO codes (en, es, pt). Internally we map to JW codes
(E, S, T) via `jw_core.languages.get_language`.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any, Protocol

from jw_core.clients.pub_media import PubMediaError
from jw_core.languages import get_language
from jw_core.news.models import NewsItem
from jw_core.news.seeds import SEED_PUB_CODES

logger = logging.getLogger(__name__)


class NewsSource(Protocol):
    """All sources implement this interface."""

    name: str
    warnings: list[str]

    async def fetch(
        self,
        *,
        languages: list[str],
        since: datetime | None,
    ) -> list[NewsItem]: ...


def _iso_to_jw(language: str) -> str:
    return get_language(language).jw_code


def _now_default() -> datetime:
    return datetime.now(UTC)


# ── Publications ────────────────────────────────────────────────────────


class PublicationsSource:
    """Watches a fixed seed list of pub_codes for new files."""

    name = "publications"

    def __init__(
        self,
        client: Any,
        *,
        seeds: list[tuple[str, bool]] | None = None,
        now: Callable[[], datetime] = _now_default,
    ) -> None:
        self._client = client
        self._seeds = list(seeds) if seeds is not None else list(SEED_PUB_CODES)
        self._now = now
        self.warnings: list[str] = []

    async def fetch(
        self,
        *,
        languages: list[str],
        since: datetime | None,  # noqa: ARG002
    ) -> list[NewsItem]:
        self.warnings = []
        items: list[NewsItem] = []
        now = self._now()
        current_issue = now.year * 100 + now.month  # YYYYMM
        for pub_code, periodical in self._seeds:
            for lang_iso in languages:
                jw_lang = _iso_to_jw(lang_iso)
                issue = current_issue if periodical else None
                try:
                    pub = await self._client.get_publication(
                        pub_code,
                        language=jw_lang,
                        issue=issue,
                    )
                except PubMediaError as exc:
                    self.warnings.append(
                        f"publications: {pub_code}/{jw_lang}{'/' + str(issue) if issue else ''} → {exc}"
                    )
                    continue
                except Exception as exc:  # noqa: BLE001
                    self.warnings.append(f"publications: unexpected error for {pub_code}/{jw_lang}: {exc!r}")
                    continue
                for f in pub.files:
                    if f.file_format.upper() not in {"EPUB", "JWPUB", "PDF"}:
                        continue
                    item_id = (
                        f"{pub_code}_{f.language}_{issue}"
                        if periodical and issue is not None
                        else f"{pub_code}_{f.language}"
                    )
                    items.append(
                        NewsItem(
                            channel="publications",
                            item_id=item_id,
                            title=f.title or pub.pub_name or pub_code,
                            language=lang_iso,
                            url=f.url,
                            description=f"{f.file_format} · {pub_code}",
                            metadata={
                                "pub_code": pub_code,
                                "format": f.file_format,
                                "issue": issue,
                                "size_bytes": f.size_bytes,
                            },
                        )
                    )
        items.sort(key=lambda i: (i.language, i.channel, i.item_id))
        return items


# ── Broadcasting ────────────────────────────────────────────────────────


_TV_URL = "https://www.jw.org/finder?wtlocale={lang}&docid={guid}"


class BroadcastingSource:
    """Watches JW Broadcasting for new videos."""

    name = "broadcasting"

    def __init__(
        self,
        client: Any,
        *,
        root: str = "VideoOnDemand",
        max_depth: int = 1,
        limit: int = 200,
    ) -> None:
        self._client = client
        self._root = root
        self._max_depth = max_depth
        self._limit = limit
        self.warnings: list[str] = []

    async def fetch(
        self,
        *,
        languages: list[str],
        since: datetime | None,  # noqa: ARG002
    ) -> list[NewsItem]:
        self.warnings = []
        items: list[NewsItem] = []
        for lang_iso in languages:
            try:
                videos = await self._client.discover_all_videos(
                    language=lang_iso,
                    root=self._root,
                    max_depth=self._max_depth,
                    limit=self._limit,
                )
            except Exception as exc:  # noqa: BLE001
                self.warnings.append(f"broadcasting: {lang_iso}: {exc!r}")
                continue
            for v in videos:
                guid = getattr(v, "guid", "") or ""
                if not guid:
                    continue
                url = getattr(v, "download_url", "") or _TV_URL.format(lang=_iso_to_jw(lang_iso), guid=guid)
                items.append(
                    NewsItem(
                        channel="broadcasting",
                        item_id=guid,
                        title=getattr(v, "title", "") or guid,
                        language=lang_iso,
                        url=url,
                        description=getattr(v, "description", "") or "",
                        first_published=_parse_first_published(getattr(v, "first_published", "")),
                        metadata={
                            "duration_seconds": float(getattr(v, "duration_seconds", 0.0) or 0.0),
                            "natural_key": getattr(v, "natural_key", ""),
                        },
                    )
                )
        items.sort(key=lambda i: (i.language, i.channel, i.item_id))
        return items


def _parse_first_published(raw: str) -> datetime | None:
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None


# ── Programs (mwb / w monthly drops) ────────────────────────────────────


class ProgramsSource:
    """Watches monthly Meeting Workbook and Watchtower Study drops."""

    name = "programs"

    def __init__(
        self,
        client: Any,
        *,
        lookahead_months: int = 2,
        now: Callable[[], datetime] = _now_default,
    ) -> None:
        self._client = client
        self._lookahead = lookahead_months
        self._now = now
        self.warnings: list[str] = []

    async def fetch(
        self,
        *,
        languages: list[str],
        since: datetime | None,  # noqa: ARG002
    ) -> list[NewsItem]:
        self.warnings = []
        items: list[NewsItem] = []
        now = self._now()
        months = _months_window(now, self._lookahead)
        for lang_iso in languages:
            jw_lang = _iso_to_jw(lang_iso)
            for year, month in months:
                issue = year * 100 + month
                for pub_code in ("mwb", "w"):
                    item_id = f"{pub_code}{year % 100:02d}.{month:02d}"
                    try:
                        pub = await self._client.get_publication(
                            pub_code,
                            language=jw_lang,
                            issue=issue,
                        )
                    except PubMediaError:
                        continue
                    except Exception as exc:  # noqa: BLE001
                        self.warnings.append(f"programs: {pub_code}/{jw_lang}/{issue}: {exc!r}")
                        continue
                    if not pub.files:
                        continue
                    epubs = [f for f in pub.files if f.file_format.upper() == "EPUB"]
                    chosen = epubs[0] if epubs else pub.files[0]
                    title = (
                        f"Meeting Workbook {year}-{month:02d}"
                        if pub_code == "mwb"
                        else f"Watchtower Study {year}-{month:02d}"
                    )
                    items.append(
                        NewsItem(
                            channel="programs",
                            item_id=item_id,
                            title=title,
                            language=lang_iso,
                            url=chosen.url,
                            description=f"{pub_code} {year}-{month:02d}",
                            metadata={
                                "pub_code": pub_code,
                                "issue": issue,
                                "year": year,
                                "month": month,
                            },
                        )
                    )
        items.sort(key=lambda i: (i.language, i.channel, i.item_id))
        return items


def _months_window(start: datetime, lookahead: int) -> list[tuple[int, int]]:
    out: list[tuple[int, int]] = []
    y, m = start.year, start.month
    for _ in range(lookahead + 1):
        out.append((y, m))
        m += 1
        if m > 12:
            m = 1
            y += 1
    return out
