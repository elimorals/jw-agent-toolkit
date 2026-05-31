"""Diff + markdown rendering for the news monitor.

This module is sync over already-collected items, except for `collect_items`
and `build_digest` which orchestrate async sources via asyncio.gather.

`render_markdown` is byte-stable: identical inputs produce identical output
(modulo the explicit `generated_at` line). It sorts items by
(language, channel, item_id) before rendering.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from jw_core.news.models import DigestReport, NewsItem, SeenRecord
from jw_core.news.sources import NewsSource
from jw_core.news.store import SeenStore

logger = logging.getLogger(__name__)


_LANG_FLAG = {
    "en": "🇬🇧 English",
    "es": "🇪🇸 Español",
    "pt": "🇵🇹 Português",
    "fr": "🇫🇷 Français",
    "de": "🇩🇪 Deutsch",
    "it": "🇮🇹 Italiano",
    "ja": "🇯🇵 日本語",
    "ko": "🇰🇷 한국어",
    "zh": "🇨🇳 中文",
    "ru": "🇷🇺 Русский",
}


_CHANNEL_LABEL = {
    "publications": "Publications",
    "broadcasting": "Broadcasting",
    "programs": "Programs",
}


async def collect_items(
    sources: list[NewsSource],
    *,
    languages: list[str],
    since: datetime | None,
) -> list[NewsItem]:
    """Run all sources concurrently and return a sorted union of items."""

    results = await asyncio.gather(
        *(s.fetch(languages=languages, since=since) for s in sources),
        return_exceptions=False,
    )
    flat: list[NewsItem] = []
    for batch in results:
        flat.extend(batch)
    flat.sort(key=lambda i: (i.language, i.channel, i.item_id))
    return flat


def diff_against_store(
    items: list[NewsItem],
    store: SeenStore,
) -> tuple[list[NewsItem], list[SeenRecord]]:
    """Split items into (new, retired).

    new      → present in `items` but missing from the store.
    retired  → present in the store but missing from `items`.
    """

    new = [i for i in items if not store.is_seen(i.channel, i.item_id)]
    current = {(i.channel, i.item_id) for i in items}
    retired = [r for r in store.all_seen() if (r.channel, r.item_id) not in current]
    new.sort(key=lambda i: (i.language, i.channel, i.item_id))
    retired.sort(key=lambda r: (r.channel, r.item_id))
    return new, retired


def render_markdown(
    *,
    new_items: list[NewsItem],
    retired: list[SeenRecord],
    generated_at: datetime,
    since: datetime | None,
    languages: list[str],
    channels: list[str],
    warnings: list[str],
) -> str:
    """Render a deterministic markdown digest."""

    new_sorted = sorted(new_items, key=lambda i: (i.language, i.channel, i.item_id))
    retired_sorted = sorted(retired, key=lambda r: (r.channel, r.item_id))

    lines: list[str] = []
    lines.append("# JW News Digest")
    lines.append("")
    lines.append(f"- Generado: {_iso(generated_at)}")
    if since is not None:
        lines.append(f"- Ventana: desde {_iso(since)}")
    else:
        lines.append("- Ventana: epoch (todo el catálogo seed)")
    lines.append(f"- Idiomas: {', '.join(languages)}")
    lines.append(f"- Canales: {', '.join(channels)}")
    lines.append(
        f"- Nuevos: {len(new_sorted)} · Retirados: {len(retired_sorted)}"
    )
    if warnings:
        lines.append(f"- Avisos: {len(warnings)}")
    lines.append("")

    by_lang: dict[str, dict[str, list[NewsItem]]] = {}
    for item in new_sorted:
        by_lang.setdefault(item.language, {}).setdefault(item.channel, []).append(item)

    for lang in languages:
        if lang not in by_lang:
            continue
        lines.append(f"## {_LANG_FLAG.get(lang, lang)}")
        lines.append("")
        for channel in channels:
            bucket = by_lang[lang].get(channel) or []
            if not bucket:
                continue
            lines.append(f"### {_CHANNEL_LABEL.get(channel, channel.title())}")
            for item in bucket:
                lines.append(_render_item_line(item))
            lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("## Retired (log-only)")
    lines.append("")
    if not retired_sorted:
        lines.append("- (none)")
    else:
        for r in retired_sorted:
            seen = _iso(r.first_seen_at)
            lines.append(f"- `{r.channel}` / `{r.item_id}` (first seen {seen})")
    lines.append("")

    if warnings:
        lines.append("## Warnings")
        lines.append("")
        for w in sorted(warnings):
            lines.append(f"- {w}")
        lines.append("")

    return "\n".join(lines)


def _render_item_line(item: NewsItem) -> str:
    bits = [f"- [{item.title}]({item.url})"]
    extras: list[str] = []
    if item.first_published is not None:
        extras.append(_iso(item.first_published))
    if item.description:
        extras.append(item.description)
    if extras:
        bits.append(" — " + " · ".join(extras))
    return "".join(bits)


def _iso(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat()


async def build_digest(
    *,
    sources: list[NewsSource],
    store: SeenStore,
    languages: list[str],
    channels: list[str],
    since: datetime | None,
    update: bool = True,
    now: datetime | None = None,
) -> DigestReport:
    """End-to-end: collect → diff → render → (optionally) update store."""

    generated_at = now or datetime.now(timezone.utc)
    items = await collect_items(sources, languages=languages, since=since)
    items = [i for i in items if i.channel in channels]
    new_items, retired_items = diff_against_store(items, store)

    warnings: list[str] = []
    for s in sources:
        warnings.extend(getattr(s, "warnings", []) or [])

    markdown = render_markdown(
        new_items=new_items,
        retired=retired_items,
        generated_at=generated_at,
        since=since,
        languages=languages,
        channels=channels,
        warnings=warnings,
    )

    if update:
        for item in items:
            store.mark_seen(item, now=generated_at)
        store.set_last_run_at(generated_at)

    return DigestReport(
        generated_at=generated_at,
        since=since,
        languages=languages,
        channels=channels,
        new_items=new_items,
        retired_items=retired_items,
        markdown=markdown,
        warnings=warnings,
    )
