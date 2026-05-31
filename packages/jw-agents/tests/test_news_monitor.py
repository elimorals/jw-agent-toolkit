"""Tests for jw_agents.news_monitor — uses stub sources via dependency injection."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from jw_core.news.models import NewsItem
from jw_core.news.store import SeenStore

from jw_agents.news_monitor import news_monitor


def _item(channel: str, item_id: str, lang: str = "en") -> NewsItem:
    return NewsItem(
        channel=channel,  # type: ignore[arg-type]
        item_id=item_id,
        title=item_id,
        language=lang,
        url=f"https://x/{item_id}",
    )


class StubSource:
    def __init__(self, items: list[NewsItem], name: str) -> None:
        self.items = items
        self.name = name
        self.warnings: list[str] = []

    async def fetch(self, *, languages, since):  # noqa: ARG002
        return [i for i in self.items if i.language in languages]


@pytest.mark.asyncio
async def test_news_monitor_returns_agent_result_with_findings(tmp_path: Path) -> None:
    store = SeenStore(path=tmp_path / "n.db")
    result = await news_monitor(
        since="epoch",
        languages=["en"],
        channels=["publications"],
        sources=[StubSource([_item("publications", "lff_E")], name="publications")],
        store=store,
        now=datetime(2026, 5, 30, tzinfo=timezone.utc),
        update=False,
    )
    assert result.agent_name == "news_monitor"
    assert len(result.findings) == 1
    f = result.findings[0]
    assert f.metadata["source"] == "news_monitor"
    assert f.citation.url == "https://x/lff_E"


@pytest.mark.asyncio
async def test_news_monitor_resolves_last_run(tmp_path: Path) -> None:
    store = SeenStore(path=tmp_path / "n.db")
    store.set_last_run_at(datetime(2026, 5, 1, tzinfo=timezone.utc))
    result = await news_monitor(
        since="last_run",
        languages=["en"],
        channels=["publications"],
        sources=[StubSource([], name="publications")],
        store=store,
        now=datetime(2026, 5, 30, tzinfo=timezone.utc),
        update=False,
    )
    assert result.metadata["since_resolved"] == "2026-05-01T00:00:00+00:00"


@pytest.mark.asyncio
async def test_news_monitor_invalid_since(tmp_path: Path) -> None:
    store = SeenStore(path=tmp_path / "n.db")
    with pytest.raises(ValueError):
        await news_monitor(
            since="yesterday",
            languages=["en"],
            channels=["publications"],
            sources=[],
            store=store,
        )
