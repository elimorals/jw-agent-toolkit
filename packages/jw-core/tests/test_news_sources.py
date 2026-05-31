"""Tests for jw_core.news.sources — with stub clients (no network)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pytest

from jw_core.clients.pub_media import PubMediaError, PubMediaFile, Publication
from jw_core.news.sources import (
    BroadcastingSource,
    ProgramsSource,
    PublicationsSource,
)


class StubPubMedia:
    """Returns canned Publication objects keyed by (pub_code, language, issue)."""

    def __init__(self, mapping: dict[tuple, Publication]) -> None:
        self.mapping = mapping
        self.calls: list[tuple] = []

    async def get_publication(
        self,
        pub_code: str,
        *,
        language: str = "E",
        issue: int | None = None,
        **_: Any,
    ) -> Publication:
        key = (pub_code, language, issue)
        self.calls.append(key)
        if key not in self.mapping:
            raise PubMediaError(f"not found: {key}")
        return self.mapping[key]


class StubBroadcasting:
    """Returns a fixed list of BroadcastingVideo regardless of input."""

    def __init__(self, videos: list[Any]) -> None:
        self.videos = videos
        self.calls = 0

    async def discover_all_videos(self, **_: Any) -> list[Any]:
        self.calls += 1
        return self.videos


def _file(url: str, fmt: str = "EPUB", language: str = "E") -> PubMediaFile:
    return PubMediaFile(
        url=url,
        filename=url.rsplit("/", 1)[-1],
        title="t",
        language=language,
        file_format=fmt,
    )


def _pub(pub_code: str, language: str = "E", files: list[PubMediaFile] | None = None) -> Publication:
    return Publication(pub_code=pub_code, pub_name=pub_code, files=files or [])


@pytest.mark.asyncio
async def test_publications_source_yields_one_item_per_file() -> None:
    stub = StubPubMedia({
        ("lff", "E", None): _pub("lff", files=[_file("https://x/lff_E.epub", "EPUB", "E")]),
        ("lff", "S", None): _pub("lff", files=[_file("https://x/lff_S.epub", "EPUB", "S")]),
    })
    src = PublicationsSource(client=stub, seeds=[("lff", False)])
    items = await src.fetch(languages=["en", "es"], since=None)
    assert len(items) == 2
    ids = {i.item_id for i in items}
    assert ids == {"lff_E", "lff_S"}
    assert all(i.channel == "publications" for i in items)


@pytest.mark.asyncio
async def test_publications_source_skips_when_404() -> None:
    stub = StubPubMedia({
        ("lff", "E", None): _pub("lff", files=[_file("https://x/lff_E.epub")]),
    })
    src = PublicationsSource(client=stub, seeds=[("lff", False), ("nonexistent", False)])
    items = await src.fetch(languages=["en"], since=None)
    # nonexistent → PubMediaError caught, no item emitted, warning attached
    assert {i.item_id for i in items} == {"lff_E"}
    assert any("nonexistent" in w for w in src.warnings)


@pytest.mark.asyncio
async def test_publications_source_periodical_uses_issue() -> None:
    now = datetime(2026, 6, 15, tzinfo=timezone.utc)
    stub = StubPubMedia({
        ("w", "E", 202606): _pub("w", files=[_file("https://x/w_E_202606.epub", "EPUB", "E")]),
    })
    src = PublicationsSource(client=stub, seeds=[("w", True)], now=lambda: now)
    items = await src.fetch(languages=["en"], since=None)
    assert {i.item_id for i in items} == {"w_E_202606"}


@pytest.mark.asyncio
async def test_broadcasting_source_basic() -> None:
    class _V:
        def __init__(self, guid: str, title: str, url: str) -> None:
            self.guid = guid
            self.title = title
            self.duration_seconds = 0.0
            self.first_published = "2026-05-28"
            self.description = ""
            self.subtitle_url = ""
            self.download_url = url
            self.tags: list[str] = []
            self.natural_key = guid

    stub = StubBroadcasting([_V("vid1", "Hello", "https://tv.jw.org/v/vid1")])
    src = BroadcastingSource(client=stub)
    items = await src.fetch(languages=["en"], since=None)
    assert len(items) == 1
    assert items[0].channel == "broadcasting"
    assert items[0].item_id == "vid1"
    assert items[0].url.startswith("https://tv.jw.org/")


@pytest.mark.asyncio
async def test_programs_source_emits_workbook_and_watchtower() -> None:
    now = datetime(2026, 6, 1, tzinfo=timezone.utc)
    stub = StubPubMedia({
        ("mwb", "E", 202606): _pub("mwb", files=[_file("https://x/mwb_E_202606.epub")]),
        ("w",   "E", 202606): _pub("w",   files=[_file("https://x/w_E_202606.epub")]),
        # 202607 + 202608 don't exist yet → 404
    })
    src = ProgramsSource(client=stub, now=lambda: now)
    items = await src.fetch(languages=["en"], since=None)
    ids = {i.item_id for i in items}
    assert "mwb26.06" in ids
    assert "w26.06" in ids
