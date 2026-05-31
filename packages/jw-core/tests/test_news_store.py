"""Tests for jw_core.news.store.SeenStore."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from jw_core.news.models import NewsItem
from jw_core.news.store import SeenStore


@pytest.fixture
def store(tmp_path: Path) -> SeenStore:
    return SeenStore(path=tmp_path / "news.db")


def _item(item_id: str = "w_E_202606", channel: str = "publications") -> NewsItem:
    return NewsItem(
        channel=channel,  # type: ignore[arg-type]
        item_id=item_id,
        title="t",
        language="en",
        url="u",
    )


def test_is_seen_false_on_empty(store: SeenStore) -> None:
    assert store.is_seen("publications", "anything") is False


def test_mark_seen_then_is_seen_true(store: SeenStore) -> None:
    store.mark_seen(_item())
    assert store.is_seen("publications", "w_E_202606") is True


def test_mark_seen_twice_keeps_first_seen(store: SeenStore) -> None:
    t0 = datetime(2026, 1, 1, tzinfo=UTC)
    t1 = datetime(2026, 5, 30, tzinfo=UTC)
    store.mark_seen(_item(), now=t0)
    store.mark_seen(_item(), now=t1)
    records = store.all_seen("publications")
    assert len(records) == 1
    assert records[0].first_seen_at == t0
    assert records[0].last_seen_at == t1


def test_all_seen_filter_by_channel(store: SeenStore) -> None:
    store.mark_seen(_item("a", "publications"))
    store.mark_seen(_item("b", "broadcasting"))
    pubs = store.all_seen("publications")
    bcst = store.all_seen("broadcasting")
    assert {r.item_id for r in pubs} == {"a"}
    assert {r.item_id for r in bcst} == {"b"}


def test_last_run_roundtrip(store: SeenStore) -> None:
    assert store.last_run_at() is None
    when = datetime(2026, 5, 30, 12, tzinfo=UTC)
    store.set_last_run_at(when)
    assert store.last_run_at() == when


def test_metadata_json_persisted_stable(store: SeenStore) -> None:
    item = NewsItem(
        channel="publications",
        item_id="x",
        title="t",
        language="en",
        url="u",
        metadata={"b": 2, "a": 1},  # insert keys out of order
    )
    store.mark_seen(item)
    record = store.all_seen("publications")[0]
    # Pydantic deserializes any JSON object; keys may come back in any order.
    assert record.metadata == {"a": 1, "b": 2}


def test_env_override(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    custom = tmp_path / "custom.db"
    monkeypatch.setenv("JW_NEWS_SEEN_DB", str(custom))
    s = SeenStore()
    s.mark_seen(_item("x"))
    assert custom.exists()
    s.close()
