"""Tests for jw_core.news.digest — deterministic diff + markdown."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from jw_core.news.digest import (
    build_digest,
    collect_items,
    diff_against_store,
    render_markdown,
)
from jw_core.news.models import NewsItem
from jw_core.news.store import SeenStore


def _item(channel: str, item_id: str, lang: str = "en", title: str | None = None) -> NewsItem:
    return NewsItem(
        channel=channel,  # type: ignore[arg-type]
        item_id=item_id,
        title=title or item_id,
        language=lang,
        url=f"https://example.org/{item_id}",
    )


class StubSource:
    def __init__(self, items: list[NewsItem], *, name: str = "stub") -> None:
        self.items = items
        self.name = name
        self.warnings: list[str] = []

    async def fetch(self, *, languages, since):  # noqa: ARG002
        return [i for i in self.items if i.language in languages]


@pytest.mark.asyncio
async def test_collect_items_runs_sources_in_parallel() -> None:
    s1 = StubSource([_item("publications", "a")])
    s2 = StubSource([_item("broadcasting", "b")])
    items = await collect_items([s1, s2], languages=["en"], since=None)
    assert {i.item_id for i in items} == {"a", "b"}


def test_diff_against_store_classifies_new_and_retired(tmp_path: Path) -> None:
    store = SeenStore(path=tmp_path / "s.db")
    store.mark_seen(_item("publications", "old"))  # in store but not in current
    items = [_item("publications", "new1"), _item("publications", "new2")]
    new, retired = diff_against_store(items, store)
    assert {i.item_id for i in new} == {"new1", "new2"}
    assert {r.item_id for r in retired} == {"old"}


def test_diff_marks_already_seen_as_not_new(tmp_path: Path) -> None:
    store = SeenStore(path=tmp_path / "s.db")
    store.mark_seen(_item("publications", "x"))
    new, retired = diff_against_store([_item("publications", "x")], store)
    assert new == []
    assert retired == []


def test_render_markdown_is_byte_stable() -> None:
    items = [
        _item("publications", "a", "en", "A"),
        _item("publications", "b", "es", "B"),
        _item("broadcasting", "c", "en", "C"),
    ]
    md1 = render_markdown(
        new_items=items,
        retired=[],
        generated_at=datetime(2026, 5, 30, 8, 0, tzinfo=timezone.utc),
        since=None,
        languages=["en", "es"],
        channels=["publications", "broadcasting", "programs"],
        warnings=[],
    )
    md2 = render_markdown(
        new_items=list(reversed(items)),  # order shouldn't matter
        retired=[],
        generated_at=datetime(2026, 5, 30, 8, 0, tzinfo=timezone.utc),
        since=None,
        languages=["en", "es"],
        channels=["publications", "broadcasting", "programs"],
        warnings=[],
    )
    assert md1 == md2


def test_render_markdown_contains_urls() -> None:
    md = render_markdown(
        new_items=[_item("publications", "w_E_202606", "en", "WT June")],
        retired=[],
        generated_at=datetime(2026, 5, 30, tzinfo=timezone.utc),
        since=None,
        languages=["en"],
        channels=["publications"],
        warnings=[],
    )
    assert "https://example.org/w_E_202606" in md
    assert "WT June" in md
    assert "### Publications" in md


@pytest.mark.asyncio
async def test_build_digest_marks_seen_when_update_true(tmp_path: Path) -> None:
    store = SeenStore(path=tmp_path / "s.db")
    src = StubSource([_item("publications", "z")])
    report = await build_digest(
        sources=[src],
        store=store,
        languages=["en"],
        channels=["publications"],
        since=None,
        update=True,
    )
    assert len(report.new_items) == 1
    assert store.is_seen("publications", "z") is True
    assert store.last_run_at() is not None


@pytest.mark.asyncio
async def test_build_digest_dry_run_does_not_mark(tmp_path: Path) -> None:
    store = SeenStore(path=tmp_path / "s.db")
    src = StubSource([_item("publications", "z")])
    report = await build_digest(
        sources=[src],
        store=store,
        languages=["en"],
        channels=["publications"],
        since=None,
        update=False,
    )
    assert len(report.new_items) == 1
    assert store.is_seen("publications", "z") is False
    assert store.last_run_at() is None
