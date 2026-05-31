"""Tests for jw_core.news.models."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from jw_core.news.models import DigestReport, NewsItem, SeenRecord


def test_news_item_minimal() -> None:
    item = NewsItem(
        channel="publications",
        item_id="w_E_202606",
        title="The Watchtower (Study) June 2026",
        language="en",
        url="https://b.jw-cdn.org/x/w_E_202606.epub",
    )
    assert item.channel == "publications"
    assert item.metadata == {}


def test_news_item_rejects_unknown_channel() -> None:
    with pytest.raises(ValueError):
        NewsItem(
            channel="podcasts",  # type: ignore[arg-type]
            item_id="x",
            title="t",
            language="en",
            url="u",
        )


def test_seen_record_roundtrip() -> None:
    now = datetime(2026, 5, 30, 8, 0, tzinfo=timezone.utc)
    record = SeenRecord(
        channel="publications",
        item_id="abc",
        first_seen_at=now,
        last_seen_at=now,
        metadata={"k": "v"},
    )
    assert record.first_seen_at == now
    assert record.metadata == {"k": "v"}


def test_digest_report_stats() -> None:
    items = [
        NewsItem(channel="publications", item_id="a", title="A", language="en", url="u"),
        NewsItem(channel="publications", item_id="b", title="B", language="es", url="u"),
        NewsItem(channel="broadcasting", item_id="c", title="C", language="en", url="u"),
    ]
    report = DigestReport(
        generated_at=datetime(2026, 5, 30, tzinfo=timezone.utc),
        since=None,
        languages=["en", "es"],
        channels=["publications", "broadcasting"],
        new_items=items,
        retired_items=[],
        markdown="# Digest",
    )
    s = report.stats()
    assert s["new"] == 3
    assert s["by_channel:publications"] == 2
    assert s["by_channel:broadcasting"] == 1
    assert s["by_channel:programs"] == 0
