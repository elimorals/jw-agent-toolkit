# Fase 25 — `news_monitor` Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship `jw news digest` — a deterministic, local-first detector of new jw.org publications, JW Broadcasting videos, and monthly workbook drops. No daemon. No LLM in the critical path. Citations on every item.

**Architecture:** New `jw_core.news` module (3 files: `store.py`, `sources.py`, `digest.py`) plus an agent wrapper `jw_agents.news_monitor`, a CLI subcommand `jw news digest`, and one MCP tool `news_digest`. Sources are async + injectable; the digest builder is sync and pure. SQLite seen-store in `~/.jw-agent-toolkit/news_seen.db`. One L1 golden case lands in `jw-eval`.

**Tech Stack:** Python 3.13 · Pydantic (models) · pytest (TDD) · SQLite (seen-store) · asyncio (source fan-out) · Typer (CLI) · FastMCP (MCP tool). Reuses `PubMediaClient`, `MediatorClient`, `JWBroadcastingClient`, `DiskCache`.

**Spec:** [`docs/superpowers/specs/2026-05-30-fase-25-news-monitor-design.md`](../specs/2026-05-30-fase-25-news-monitor-design.md).

---

## File map

Creates:
- `packages/jw-core/src/jw_core/news/__init__.py`
- `packages/jw-core/src/jw_core/news/models.py`
- `packages/jw-core/src/jw_core/news/store.py`
- `packages/jw-core/src/jw_core/news/seeds.py`
- `packages/jw-core/src/jw_core/news/sources.py`
- `packages/jw-core/src/jw_core/news/digest.py`
- `packages/jw-core/tests/test_news_models.py`
- `packages/jw-core/tests/test_news_store.py`
- `packages/jw-core/tests/test_news_sources.py`
- `packages/jw-core/tests/test_news_digest.py`
- `packages/jw-agents/src/jw_agents/news_monitor.py`
- `packages/jw-agents/tests/test_news_monitor.py`
- `packages/jw-cli/src/jw_cli/commands/news.py`
- `packages/jw-cli/tests/test_news_cli.py`
- `packages/jw-eval/fixtures/golden_qa/l1/news_monitor_digest_en.yaml`
- `docs/guias/monitor-de-novedades.md`

Modifies:
- `packages/jw-cli/src/jw_cli/main.py` — register `news` Typer sub-app.
- `packages/jw-cli/src/jw_cli/commands/__init__.py` — re-export `news`.
- `packages/jw-mcp/src/jw_mcp/server.py` — register `news_digest` tool.
- `docs/ROADMAP.md` — add Fase 25 section.
- `docs/VISION_AUDIT.md` — add Fase 25 row.
- `docs/README.md` — link the new guide.

---

### Task 1: Models for news items + reports

**Files:**
- Create: `packages/jw-core/src/jw_core/news/__init__.py`
- Create: `packages/jw-core/src/jw_core/news/models.py`
- Create: `packages/jw-core/tests/test_news_models.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/jw-core/tests/test_news_models.py
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
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest packages/jw-core/tests/test_news_models.py -v`
Expected: FAIL — `jw_core.news.models` not found.

- [ ] **Step 3: Implement models**

```python
# packages/jw-core/src/jw_core/news/__init__.py
"""News monitor — detect new jw.org publications, broadcasting videos, and
monthly meeting program drops.

Public API:
    from jw_core.news import (
        NewsItem, SeenRecord, DigestReport,
        SeenStore,
        PublicationsSource, BroadcastingSource, ProgramsSource, NewsSource,
        build_digest, collect_items, diff_against_store, render_markdown,
    )
"""

from jw_core.news.digest import (
    build_digest,
    collect_items,
    diff_against_store,
    render_markdown,
)
from jw_core.news.models import DigestReport, NewsItem, SeenRecord
from jw_core.news.sources import (
    BroadcastingSource,
    NewsSource,
    ProgramsSource,
    PublicationsSource,
)
from jw_core.news.store import SeenStore

__all__ = [
    "BroadcastingSource",
    "DigestReport",
    "NewsItem",
    "NewsSource",
    "ProgramsSource",
    "PublicationsSource",
    "SeenRecord",
    "SeenStore",
    "build_digest",
    "collect_items",
    "diff_against_store",
    "render_markdown",
]
```

```python
# packages/jw-core/src/jw_core/news/models.py
"""Pydantic models for the news monitor.

NewsItem — one piece of upstream content (a magazine, a video, a workbook).
SeenRecord — what's already in the local store.
DigestReport — what the CLI / MCP tool returns; serializable.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

Channel = Literal["publications", "broadcasting", "programs"]


class NewsItem(BaseModel):
    """One upstream item observed in a source's current response."""

    channel: Channel
    item_id: str
    title: str
    language: str
    url: str
    description: str = ""
    first_published: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class SeenRecord(BaseModel):
    """A row from the local seen-store."""

    channel: str
    item_id: str
    first_seen_at: datetime
    last_seen_at: datetime
    metadata: dict[str, Any] = Field(default_factory=dict)


class DigestReport(BaseModel):
    """Aggregate result of one digest run."""

    generated_at: datetime
    since: datetime | None
    languages: list[str]
    channels: list[str]
    new_items: list[NewsItem]
    retired_items: list[SeenRecord]
    markdown: str
    warnings: list[str] = Field(default_factory=list)

    def stats(self) -> dict[str, int]:
        base = {
            "new": len(self.new_items),
            "retired": len(self.retired_items),
            "by_channel:publications": 0,
            "by_channel:broadcasting": 0,
            "by_channel:programs": 0,
        }
        for item in self.new_items:
            key = f"by_channel:{item.channel}"
            base[key] = base.get(key, 0) + 1
        return base
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `uv run pytest packages/jw-core/tests/test_news_models.py -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add packages/jw-core/src/jw_core/news/__init__.py \
        packages/jw-core/src/jw_core/news/models.py \
        packages/jw-core/tests/test_news_models.py
git commit -m "feat(news): scaffold news models (NewsItem/SeenRecord/DigestReport)"
```

> **NOTE**: the import in `__init__.py` references `store`, `sources`, `digest` that don't exist yet. The commit will fail to import until later tasks are done. Either (a) temporarily comment out those imports — recommended — and uncomment in Task 12, or (b) accept that `from jw_core.news import NewsItem` works only after Task 4. Choose (a) by leaving only the model imports in `__init__.py` until then:

```python
# Temporary minimal __init__.py:
from jw_core.news.models import DigestReport, NewsItem, SeenRecord
__all__ = ["DigestReport", "NewsItem", "SeenRecord"]
```

Restore the full `__init__.py` shape in Task 12 (wiring).

---

### Task 2: Seen-store (SQLite + last_run tracking)

**Files:**
- Create: `packages/jw-core/src/jw_core/news/store.py`
- Create: `packages/jw-core/tests/test_news_store.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/jw-core/tests/test_news_store.py
"""Tests for jw_core.news.store.SeenStore."""

from __future__ import annotations

from datetime import datetime, timezone
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
    t0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
    t1 = datetime(2026, 5, 30, tzinfo=timezone.utc)
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
    when = datetime(2026, 5, 30, 12, tzinfo=timezone.utc)
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
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest packages/jw-core/tests/test_news_store.py -v`
Expected: FAIL — `jw_core.news.store` missing.

- [ ] **Step 3: Implement the store**

```python
# packages/jw-core/src/jw_core/news/store.py
"""Local SQLite store of items the news monitor has already reported.

Schema:
    news_seen(channel, item_id, first_seen_at, last_seen_at, metadata_json)
    news_runs(id=1, last_run_at)

Both timestamps are stored as ISO-8601 UTC strings.

Default path: ~/.jw-agent-toolkit/news_seen.db (env: JW_NEWS_SEEN_DB).
"""

from __future__ import annotations

import json
import os
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path

from jw_core.news.models import NewsItem, SeenRecord

_SCHEMA = """
CREATE TABLE IF NOT EXISTS news_seen (
    channel TEXT NOT NULL,
    item_id TEXT NOT NULL,
    first_seen_at TEXT NOT NULL,
    last_seen_at TEXT NOT NULL,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    PRIMARY KEY (channel, item_id)
);
CREATE INDEX IF NOT EXISTS idx_news_seen_last_seen ON news_seen(last_seen_at);

CREATE TABLE IF NOT EXISTS news_runs (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    last_run_at TEXT NOT NULL
);
"""


def _default_path() -> Path:
    env = os.getenv("JW_NEWS_SEEN_DB")
    if env:
        return Path(env).expanduser()
    return Path("~/.jw-agent-toolkit/news_seen.db").expanduser()


def _iso(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat()


def _from_iso(s: str) -> datetime:
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


class SeenStore:
    """Tiny SQLite store of (channel, item_id) sightings + last_run."""

    def __init__(self, path: Path | str | None = None) -> None:
        self.path = Path(path).expanduser() if path else _default_path()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(
            self.path,
            isolation_level=None,
            check_same_thread=False,
        )
        self._lock = threading.Lock()
        with self._lock:
            self._conn.executescript(_SCHEMA)
            self._conn.execute("PRAGMA journal_mode=WAL")

    def is_seen(self, channel: str, item_id: str) -> bool:
        with self._lock:
            row = self._conn.execute(
                "SELECT 1 FROM news_seen WHERE channel = ? AND item_id = ?",
                (channel, item_id),
            ).fetchone()
        return row is not None

    def mark_seen(self, item: NewsItem, *, now: datetime | None = None) -> None:
        ts = _iso(now or datetime.now(timezone.utc))
        metadata = json.dumps(
            item.metadata or {}, separators=(",", ":"), sort_keys=True
        )
        with self._lock:
            existing = self._conn.execute(
                "SELECT first_seen_at FROM news_seen WHERE channel = ? AND item_id = ?",
                (item.channel, item.item_id),
            ).fetchone()
            first_seen = existing[0] if existing else ts
            self._conn.execute(
                "INSERT OR REPLACE INTO news_seen "
                "(channel, item_id, first_seen_at, last_seen_at, metadata_json) "
                "VALUES (?, ?, ?, ?, ?)",
                (item.channel, item.item_id, first_seen, ts, metadata),
            )

    def all_seen(self, channel: str | None = None) -> list[SeenRecord]:
        sql = "SELECT channel, item_id, first_seen_at, last_seen_at, metadata_json FROM news_seen"
        params: tuple = ()
        if channel is not None:
            sql += " WHERE channel = ?"
            params = (channel,)
        sql += " ORDER BY channel, item_id"
        with self._lock:
            rows = self._conn.execute(sql, params).fetchall()
        return [
            SeenRecord(
                channel=r[0],
                item_id=r[1],
                first_seen_at=_from_iso(r[2]),
                last_seen_at=_from_iso(r[3]),
                metadata=json.loads(r[4] or "{}"),
            )
            for r in rows
        ]

    def last_run_at(self) -> datetime | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT last_run_at FROM news_runs WHERE id = 1"
            ).fetchone()
        return _from_iso(row[0]) if row else None

    def set_last_run_at(self, when: datetime) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT OR REPLACE INTO news_runs (id, last_run_at) VALUES (1, ?)",
                (_iso(when),),
            )

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    def __enter__(self) -> SeenStore:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `uv run pytest packages/jw-core/tests/test_news_store.py -v`
Expected: 7 passed.

- [ ] **Step 5: Commit**

```bash
git add packages/jw-core/src/jw_core/news/store.py \
        packages/jw-core/tests/test_news_store.py
git commit -m "feat(news): SeenStore — SQLite seen-store with last_run tracking"
```

---

### Task 3: Seeds (hard-coded pub_code list for publications)

**Files:**
- Create: `packages/jw-core/src/jw_core/news/seeds.py`

- [ ] **Step 1: Write the seed file (no test — data only)**

```python
# packages/jw-core/src/jw_core/news/seeds.py
"""Seed publication codes watched by PublicationsSource.

Hand-curated; audit annually. Each entry is (pub_code, is_periodical).
- Periodicals require an `issue=YYYYMM` to resolve a concrete file.
- Non-periodicals (books, brochures) resolve to the latest published edition.

Stable since 2026-05-30. Source: jw.org publication catalog.
"""

from __future__ import annotations

PERIODICALS: tuple[str, ...] = (
    "w",        # Watchtower (Study Edition)
    "wp",       # Watchtower (Public Edition)
    "g",        # Awake!
    "mwb",      # Meeting Workbook
)

NON_PERIODICALS: tuple[str, ...] = (
    "lff",      # Enjoy Life Forever! (current study book)
    "bhs",      # What Can the Bible Teach Us?
    "ll",       # Listen to God and Live Forever
    "lmd",      # Love People — Make Disciples
    "rj",       # Return to Jehovah
    "rk",       # The Kingdom Rules!
    "jy",       # Jesus — the Way, the Truth, the Life
    "ia",       # Imitate Their Faith
    "ed",       # Enjoy Life Forever brochure
    "fg",       # Good News
    "es",       # Yearbook (legacy; harmless if 404)
)

SEED_PUB_CODES: tuple[tuple[str, bool], ...] = tuple(
    [(code, True) for code in PERIODICALS] + [(code, False) for code in NON_PERIODICALS]
)
```

- [ ] **Step 2: Commit**

```bash
git add packages/jw-core/src/jw_core/news/seeds.py
git commit -m "feat(news): seed pub_code list for PublicationsSource"
```

---

### Task 4: NewsSource protocol + three implementations

**Files:**
- Create: `packages/jw-core/src/jw_core/news/sources.py`
- Create: `packages/jw-core/tests/test_news_sources.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/jw-core/tests/test_news_sources.py
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
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest packages/jw-core/tests/test_news_sources.py -v`
Expected: FAIL — `jw_core.news.sources` missing.

- [ ] **Step 3: Implement the three sources**

```python
# packages/jw-core/src/jw_core/news/sources.py
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
from datetime import datetime, timezone
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
    return datetime.now(timezone.utc)


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
                        f"publications: {pub_code}/{jw_lang}"
                        f"{'/' + str(issue) if issue else ''} → {exc}"
                    )
                    continue
                except Exception as exc:  # noqa: BLE001
                    self.warnings.append(
                        f"publications: unexpected error for {pub_code}/{jw_lang}: {exc!r}"
                    )
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
                url = getattr(v, "download_url", "") or _TV_URL.format(
                    lang=_iso_to_jw(lang_iso), guid=guid
                )
                items.append(
                    NewsItem(
                        channel="broadcasting",
                        item_id=guid,
                        title=getattr(v, "title", "") or guid,
                        language=lang_iso,
                        url=url,
                        description=getattr(v, "description", "") or "",
                        first_published=_parse_first_published(
                            getattr(v, "first_published", "")
                        ),
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
            for (year, month) in months:
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
                        self.warnings.append(
                            f"programs: {pub_code}/{jw_lang}/{issue}: {exc!r}"
                        )
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
```

- [ ] **Step 4: Run the test to verify it passes**

The tests use `@pytest.mark.asyncio`. Ensure `pytest-asyncio` is already in the dev deps (it is — used elsewhere in the toolkit).

Run: `uv run pytest packages/jw-core/tests/test_news_sources.py -v`
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add packages/jw-core/src/jw_core/news/sources.py \
        packages/jw-core/tests/test_news_sources.py
git commit -m "feat(news): three NewsSource implementations (publications/broadcasting/programs)"
```

---

### Task 5: Diff + markdown rendering (digest core)

**Files:**
- Create: `packages/jw-core/src/jw_core/news/digest.py`
- Create: `packages/jw-core/tests/test_news_digest.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/jw-core/tests/test_news_digest.py
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
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest packages/jw-core/tests/test_news_digest.py -v`
Expected: FAIL — `jw_core.news.digest` missing.

- [ ] **Step 3: Implement the digest core**

```python
# packages/jw-core/src/jw_core/news/digest.py
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
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `uv run pytest packages/jw-core/tests/test_news_digest.py -v`
Expected: 7 passed.

- [ ] **Step 5: Commit**

```bash
git add packages/jw-core/src/jw_core/news/digest.py \
        packages/jw-core/tests/test_news_digest.py
git commit -m "feat(news): digest builder — collect + diff + render markdown"
```

---

### Task 6: Restore full `__init__.py` re-exports

**Files:**
- Modify: `packages/jw-core/src/jw_core/news/__init__.py`

- [ ] **Step 1: Replace the temporary minimal `__init__.py` with the full export list from Task 1, Step 3**

Use the *first* block from Task 1's Step 3 (the one re-exporting `SeenStore`, sources, and digest helpers).

- [ ] **Step 2: Run all news tests together**

Run: `uv run pytest packages/jw-core/tests/test_news_models.py packages/jw-core/tests/test_news_store.py packages/jw-core/tests/test_news_sources.py packages/jw-core/tests/test_news_digest.py -v`
Expected: all green.

- [ ] **Step 3: Commit**

```bash
git add packages/jw-core/src/jw_core/news/__init__.py
git commit -m "feat(news): export full news API from package __init__"
```

---

### Task 7: Agent wrapper `news_monitor`

**Files:**
- Create: `packages/jw-agents/src/jw_agents/news_monitor.py`
- Create: `packages/jw-agents/tests/test_news_monitor.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/jw-agents/tests/test_news_monitor.py
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
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest packages/jw-agents/tests/test_news_monitor.py -v`
Expected: FAIL — `jw_agents.news_monitor` missing.

- [ ] **Step 3: Implement the agent**

```python
# packages/jw-agents/src/jw_agents/news_monitor.py
"""news_monitor agent — thin async wrapper that wires sources to the digest
builder and returns an `AgentResult` with one `Finding` per new item.

Default behaviour wires real clients via `jw_core.clients.factory.build_clients`,
but tests/eval can inject stub sources + a stub store for full isolation.

Returns an AgentResult so MCP/CLI surfaces see the same envelope as every
other agent.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from jw_core.clients.factory import build_clients
from jw_core.clients.jw_broadcasting import JWBroadcastingClient
from jw_core.news.digest import build_digest
from jw_core.news.models import DigestReport
from jw_core.news.sources import (
    BroadcastingSource,
    NewsSource,
    ProgramsSource,
    PublicationsSource,
)
from jw_core.news.store import SeenStore

from jw_agents.base import AgentResult, Citation, Finding

logger = logging.getLogger(__name__)

DEFAULT_LANGUAGES = ["en", "es", "pt"]
DEFAULT_CHANNELS = ["publications", "broadcasting", "programs"]


def _resolve_since(since: str | None, store: SeenStore) -> datetime | None:
    if since is None or since == "last_run":
        return store.last_run_at()
    if since == "epoch":
        return None
    try:
        dt = datetime.fromisoformat(since)
    except ValueError as exc:
        raise ValueError(
            f"--since must be 'last_run', 'epoch' or ISO-8601 date, got {since!r}"
        ) from exc
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _default_sources() -> list[NewsSource]:
    clients = build_clients()
    bcst = JWBroadcastingClient(
        throttler=clients.throttler,
        cache=clients.cache,
        telemetry=clients.telemetry,
    )
    return [
        PublicationsSource(client=clients.pub_media),
        BroadcastingSource(client=bcst),
        ProgramsSource(client=clients.pub_media),
    ]


async def news_monitor(
    *,
    since: str | None = "last_run",
    languages: list[str] | None = None,
    channels: list[str] | None = None,
    sources: list[NewsSource] | None = None,
    store: SeenStore | None = None,
    update: bool = True,
    now: datetime | None = None,
) -> AgentResult:
    """Run the news monitor and return an AgentResult.

    Args:
        since: "last_run" (default), "epoch", or an ISO date string.
        languages: ISO codes (en/es/pt/...). Default ["en","es","pt"].
        channels: subset of {"publications","broadcasting","programs"}.
        sources: inject stubs for testing; default wires real clients.
        store: inject for tests; default SeenStore() uses ~/.jw-agent-toolkit/.
        update: when True, mark seen items and advance last_run.
        now: clock injection for determinism in tests.
    """

    languages = languages or DEFAULT_LANGUAGES
    channels = channels or DEFAULT_CHANNELS
    owned_store = store is None
    store = store or SeenStore()
    owned_sources = sources is None
    sources = sources if sources is not None else _default_sources()

    try:
        since_dt = _resolve_since(since, store)
        report: DigestReport = await build_digest(
            sources=sources,
            store=store,
            languages=languages,
            channels=channels,
            since=since_dt,
            update=update,
            now=now,
        )
    finally:
        if owned_store:
            store.close()
        if owned_sources:
            # Real clients own httpx; close them so we don't leak.
            for s in sources:
                client = getattr(s, "_client", None)
                aclose = getattr(client, "aclose", None)
                if aclose:
                    try:
                        await aclose()
                    except Exception as exc:  # noqa: BLE001
                        logger.debug("source close failed: %s", exc)

    result = AgentResult(query=f"news_digest since={since}", agent_name="news_monitor")
    result.metadata.update(
        {
            "since": since,
            "since_resolved": since_dt.isoformat() if since_dt else "epoch",
            "languages": languages,
            "channels": channels,
            "stats": report.stats(),
            "markdown": report.markdown,
            "warnings": report.warnings,
            "retired": [r.model_dump(mode="json") for r in report.retired_items],
        }
    )
    for item in report.new_items:
        result.findings.append(
            Finding(
                summary=f"[{item.channel}/{item.language}] {item.title}",
                citation=Citation(
                    url=item.url,
                    title=item.title,
                    kind=item.channel,
                    metadata=item.metadata,
                ),
                excerpt=item.description,
                metadata={
                    "source": "news_monitor",
                    "channel": item.channel,
                    "item_id": item.item_id,
                    "language": item.language,
                },
            )
        )
    for w in report.warnings:
        result.warnings.append(w)
    return result
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `uv run pytest packages/jw-agents/tests/test_news_monitor.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add packages/jw-agents/src/jw_agents/news_monitor.py \
        packages/jw-agents/tests/test_news_monitor.py
git commit -m "feat(news): news_monitor agent wraps sources + store into AgentResult"
```

---

### Task 8: CLI subcommand `jw news digest`

**Files:**
- Create: `packages/jw-cli/src/jw_cli/commands/news.py`
- Create: `packages/jw-cli/tests/test_news_cli.py`
- Modify: `packages/jw-cli/src/jw_cli/main.py`
- Modify: `packages/jw-cli/src/jw_cli/commands/__init__.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/jw-cli/tests/test_news_cli.py
"""Smoke tests for `jw news digest`. Uses CliRunner with stubbed agent."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from jw_agents.base import AgentResult, Citation, Finding
from jw_cli.commands.news import news_app

runner = CliRunner()


def _fake_agent_result() -> AgentResult:
    r = AgentResult(query="news_digest since=epoch", agent_name="news_monitor")
    r.findings.append(
        Finding(
            summary="[publications/en] WT June 2026",
            citation=Citation(url="https://x/w_E_202606.epub", title="WT June 2026"),
            metadata={
                "source": "news_monitor",
                "channel": "publications",
                "item_id": "w_E_202606",
                "language": "en",
            },
        )
    )
    r.metadata["markdown"] = "# JW News Digest\n\n- 1 nuevo\n"
    r.metadata["stats"] = {"new": 1, "retired": 0}
    return r


async def _stub_news_monitor(**_: object) -> AgentResult:
    return _fake_agent_result()


def test_news_digest_prints_markdown_by_default() -> None:
    with patch("jw_cli.commands.news.news_monitor", new=_stub_news_monitor):
        result = runner.invoke(news_app, ["digest", "--since", "epoch", "--channels", "publications"])
    assert result.exit_code == 0
    assert "# JW News Digest" in result.stdout


def test_news_digest_writes_out_file(tmp_path: Path) -> None:
    out = tmp_path / "digest.md"
    with patch("jw_cli.commands.news.news_monitor", new=_stub_news_monitor):
        result = runner.invoke(
            news_app,
            ["digest", "--since", "epoch", "--out", str(out)],
        )
    assert result.exit_code == 0
    assert out.read_text().startswith("# JW News Digest")


def test_news_digest_json_format() -> None:
    with patch("jw_cli.commands.news.news_monitor", new=_stub_news_monitor):
        result = runner.invoke(news_app, ["digest", "--since", "epoch", "--json"])
    assert result.exit_code == 0
    # JSON output must include the stats key.
    assert '"stats"' in result.stdout or '"markdown"' in result.stdout
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest packages/jw-cli/tests/test_news_cli.py -v`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement the CLI**

```python
# packages/jw-cli/src/jw_cli/commands/news.py
"""`jw news digest` — print a markdown digest of new jw.org content.

Usage:
    jw news digest                                  # last_run, all channels, default langs
    jw news digest --since 2026-05-23
    jw news digest --since epoch --no-update
    jw news digest --languages en,es --channels publications,programs --out digest.md
    jw news digest --json
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import typer
from rich.console import Console

from jw_agents.news_monitor import (
    DEFAULT_CHANNELS,
    DEFAULT_LANGUAGES,
    news_monitor,
)

news_app = typer.Typer(
    name="news",
    help="Monitor de novedades jw.org (publicaciones, broadcasting, programas).",
    no_args_is_help=True,
    add_completion=False,
)

console = Console()
err_console = Console(stderr=True)


def _csv(value: str | None, default: list[str]) -> list[str]:
    if not value:
        return list(default)
    return [v.strip() for v in value.split(",") if v.strip()]


@news_app.command("digest")
def digest_cmd(
    since: str = typer.Option(
        "last_run",
        "--since",
        help='"last_run" (default), "epoch", or ISO date 2026-05-23.',
    ),
    languages: str = typer.Option(
        "",
        "--languages",
        "-l",
        help=f"CSV of ISO codes. Default: {','.join(DEFAULT_LANGUAGES)}.",
    ),
    channels: str = typer.Option(
        "",
        "--channels",
        "-c",
        help=f"CSV of channel names. Default: {','.join(DEFAULT_CHANNELS)}.",
    ),
    out: Path | None = typer.Option(None, "--out", "-o", help="Write digest to file."),
    no_update: bool = typer.Option(
        False,
        "--no-update",
        help="Do not mark seen items or advance last_run (dry mode).",
    ),
    json_format: bool = typer.Option(
        False,
        "--json",
        help="Emit JSON envelope instead of markdown.",
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Print a digest of new jw.org content."""

    if verbose:
        import logging

        logging.basicConfig(level=logging.DEBUG)

    langs = _csv(languages, DEFAULT_LANGUAGES)
    chans = _csv(channels, DEFAULT_CHANNELS)
    invalid = [c for c in chans if c not in DEFAULT_CHANNELS]
    if invalid:
        err_console.print(f"[red]Unknown channels: {invalid}. Valid: {DEFAULT_CHANNELS}[/red]")
        raise typer.Exit(2)

    try:
        result = asyncio.run(
            news_monitor(
                since=since,
                languages=langs,
                channels=chans,
                update=not no_update,
            )
        )
    except ValueError as exc:
        err_console.print(f"[red]Invalid argument: {exc}[/red]")
        raise typer.Exit(2) from exc

    if json_format:
        payload = {
            "agent_name": result.agent_name,
            "stats": result.metadata.get("stats", {}),
            "markdown": result.metadata.get("markdown", ""),
            "warnings": result.warnings,
            "findings": [
                {
                    "summary": f.summary,
                    "url": f.citation.url,
                    "metadata": f.metadata,
                }
                for f in result.findings
            ],
        }
        text = json.dumps(payload, indent=2, ensure_ascii=False)
    else:
        text = result.metadata.get("markdown", "(empty digest)")

    if out is not None:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="utf-8")
        err_console.print(f"[green]Wrote digest to {out}[/green]")
    console.print(text)

    if result.warnings:
        err_console.print(f"[yellow]{len(result.warnings)} warnings:[/yellow]")
        for w in result.warnings:
            err_console.print(f"  - {w}")
```

- [ ] **Step 4: Register in CLI**

Edit `packages/jw-cli/src/jw_cli/commands/__init__.py`:

```python
# add at the end of the import block
from jw_cli.commands import news as news  # noqa: F401
```

Edit `packages/jw-cli/src/jw_cli/main.py` — add to the existing imports list:

```python
from jw_cli.commands import (
    chapter,
    daily,
    download,
    jwpub,
    languages,
    ministry,
    news,
    search,
    topic,
    verse,
    workbook,
)
```

…and after `app.add_typer(ministry.ministry_app, name="ministry")`:

```python
app.add_typer(news.news_app, name="news")
```

- [ ] **Step 5: Run the CLI test**

Run: `uv run pytest packages/jw-cli/tests/test_news_cli.py -v`
Expected: 3 passed.

- [ ] **Step 6: Commit**

```bash
git add packages/jw-cli/src/jw_cli/commands/news.py \
        packages/jw-cli/src/jw_cli/commands/__init__.py \
        packages/jw-cli/src/jw_cli/main.py \
        packages/jw-cli/tests/test_news_cli.py
git commit -m "feat(cli): jw news digest — markdown/json digest of new jw.org content"
```

---

### Task 9: MCP tool `news_digest`

**Files:**
- Modify: `packages/jw-mcp/src/jw_mcp/server.py`

- [ ] **Step 1: Add the import (near other agent imports)**

Find the block of `from jw_agents ...` imports in `server.py` and add:

```python
from jw_agents.news_monitor import news_monitor as news_monitor_agent
```

- [ ] **Step 2: Register the tool**

Append (above the `if __name__ == "__main__":` block — or wherever the last `@mcp.tool` lives):

```python
@mcp.tool
async def news_digest(
    since: str | None = "last_run",
    languages: list[str] | None = None,
    channels: list[str] | None = None,
    update: bool = True,
) -> dict[str, Any]:
    """Run the news monitor and return the deterministic digest.

    Args:
        since: "last_run" (default), "epoch", or an ISO-8601 date (e.g.
            "2026-05-23"). Drives the human-facing "Ventana:" line of the
            digest; new/retired classification still uses the local seen-store.
        languages: ISO codes (en/es/pt/...). Default ["en","es","pt"].
        channels: subset of {"publications","broadcasting","programs"}.
            Default all three.
        update: when True, mark new items as seen and advance last_run.
            Use False from interactive sessions to preview without committing.

    Returns:
        Dict with `markdown` (ready to render), `stats`, `findings`,
        `warnings`, and `retired_items`. Cite each `findings[i].citation.url`.
    """

    try:
        result = await news_monitor_agent(
            since=since,
            languages=languages,
            channels=channels,
            update=update,
        )
    except ValueError as exc:
        return {"error": str(exc)}
    return result.to_dict() | {
        "markdown": result.metadata.get("markdown", ""),
        "stats": result.metadata.get("stats", {}),
        "since_resolved": result.metadata.get("since_resolved"),
    }
```

- [ ] **Step 3: Smoke-test by importing**

Run:
```bash
uv run python -c "from jw_mcp.server import mcp; print('OK', sum(1 for _ in mcp._tools))"
```
Expected: prints `OK <N>` with N greater than the previous tool count by 1.

- [ ] **Step 4: Commit**

```bash
git add packages/jw-mcp/src/jw_mcp/server.py
git commit -m "feat(mcp): news_digest tool exposes news_monitor agent"
```

---

### Task 10: L1 golden case for jw-eval

**Files:**
- Create: `packages/jw-eval/fixtures/golden_qa/l1/news_monitor_digest_en.yaml`
- Modify (only if Fase 22 is shipped and the adapter file exists): `packages/jw-eval/src/jw_eval/agent_adapters.py`

- [ ] **Step 1: Write the YAML**

```yaml
# packages/jw-eval/fixtures/golden_qa/l1/news_monitor_digest_en.yaml
id: l1_news_monitor_digest_en
agent: news_monitor
layer: l1
input:
  since: epoch
  languages: [en]
  channels: [publications]
  # The eval adapter wires stub sources so this case is deterministic +
  # network-free. See packages/jw-eval/src/jw_eval/agent_adapters.py for the
  # stub stub-source registration.
  _adapter: stub_news_monitor_with_one_item
expected:
  min_findings: 1
  must_have_source: news_monitor
  must_have_citation: true
  forbidden_keywords_in_findings:
    - "(none)"  # the digest's empty marker must not leak into a finding
metadata:
  topic: news.publications
  fase: 25
  added_by: elias
  added_at: 2026-05-30
```

- [ ] **Step 2: Note (no test step here)** — the case will fail to run until the `agent_adapters` wiring exists in jw-eval. That wiring lives inside Fase 22's plan (Task 11 there) or its forthcoming refactor. If `jw-eval` is not yet shipped at the time this task runs, skip; otherwise add a stub adapter:

```python
# packages/jw-eval/src/jw_eval/agent_adapters.py  (only append, do not rewrite)
def stub_news_monitor_with_one_item():
    """Return a callable agent(input_dict) -> AgentResult-like with one finding."""

    from jw_agents.news_monitor import news_monitor as _real
    from jw_core.news.models import NewsItem
    from jw_core.news.store import SeenStore

    class _StubSource:
        name = "publications"
        warnings: list[str] = []
        async def fetch(self, *, languages, since):  # noqa: ARG002
            return [
                NewsItem(
                    channel="publications",
                    item_id="lff_E",
                    title="Enjoy Life Forever — EN",
                    language="en",
                    url="https://example.org/lff_E.epub",
                )
            ]

    async def runner(input_dict):
        import tempfile
        from pathlib import Path
        tmp = Path(tempfile.mkdtemp()) / "news.db"
        store = SeenStore(path=tmp)
        return await _real(
            since=input_dict.get("since", "epoch"),
            languages=input_dict.get("languages", ["en"]),
            channels=input_dict.get("channels", ["publications"]),
            sources=[_StubSource()],
            store=store,
            update=False,
        )
    return runner
```

- [ ] **Step 3: Commit (combined with the YAML)**

```bash
git add packages/jw-eval/fixtures/golden_qa/l1/news_monitor_digest_en.yaml
# only if you also wrote the adapter:
git add packages/jw-eval/src/jw_eval/agent_adapters.py 2>/dev/null || true
git commit -m "feat(eval): L1 golden case for news_monitor (Fase 25)"
```

---

### Task 11: Full-suite regression check

**Files:** none (verification only).

- [ ] **Step 1: Run the entire test suite**

Run: `uv run pytest packages/ -v --tb=short`
Expected: previous 551 tests still pass + ~20 new tests from Fase 25 are green. No regressions elsewhere.

- [ ] **Step 2: Ruff + format**

```bash
uv run ruff check packages/jw-core/src/jw_core/news \
                  packages/jw-agents/src/jw_agents/news_monitor.py \
                  packages/jw-cli/src/jw_cli/commands/news.py
uv run ruff format --check packages/jw-core/src/jw_core/news \
                            packages/jw-agents/src/jw_agents/news_monitor.py \
                            packages/jw-cli/src/jw_cli/commands/news.py
```
Expected: zero violations.

- [ ] **Step 3: Mypy on new code (best effort)**

```bash
uv run mypy packages/jw-core/src/jw_core/news \
            packages/jw-agents/src/jw_agents/news_monitor.py \
            packages/jw-cli/src/jw_cli/commands/news.py
```
Expected: no new errors. Pre-existing errors elsewhere ignored.

- [ ] **Step 4: CLI smoke (will hit network if you run without `--since=epoch --no-update`!)**

```bash
# Network-free smoke via the CLI: invoke `--help` only.
uv run jw news --help
uv run jw news digest --help
```
Expected: help text prints, exit code 0.

- [ ] **Step 5: Commit if anything was tweaked**

If steps 2-4 surfaced minor fixes, commit them under a single tidy commit. Otherwise, nothing to do.

---

### Task 12: Documentation — user guide

**Files:**
- Create: `docs/guias/monitor-de-novedades.md`
- Modify: `docs/README.md`

- [ ] **Step 1: Write the guide**

```markdown
# Monitor de novedades jw.org (`jw news digest`)

> Fase 25 — detector determinista de novedades en publicaciones, JW Broadcasting y programa mensual.
> Spec: `docs/superpowers/specs/2026-05-30-fase-25-news-monitor-design.md`.

## Para qué sirve

Te muestra qué hay nuevo en jw.org desde la última vez que ejecutaste el comando, sin tener que entrar manualmente a Atalaya, ¡Despertad!, tv.jw.org y WOL.

Tres canales:

| Canal | Qué detecta | TTL del catálogo |
|---|---|---|
| `publications` | Atalaya, ¡Despertad!, libros activos, brochures | 6h |
| `broadcasting` | Videos nuevos en tv.jw.org (raíz `VideoOnDemand`) | 24h |
| `programs` | Workbook `mwb_YYYYMM` y Atalaya estudio `w_YYYYMM` | 7 días |

## Uso

```bash
# Primera vez — marca todo como visto sin imprimir spam
jw news digest --since 2026-05-30 --languages en --channels publications --out /tmp/seed.md

# Uso normal — desde el último run
jw news digest

# Filtros
jw news digest --languages en,es --channels publications,programs

# Modo dry — no actualiza la base local
jw news digest --since epoch --no-update

# JSON para programar contra él
jw news digest --json > digest.json

# A archivo
jw news digest --out ~/Documents/jw-news/$(date +%F).md
```

### Argumentos clave

| Flag | Default | Notas |
|---|---|---|
| `--since` | `last_run` | También acepta `epoch` o una fecha ISO `2026-05-23` |
| `--languages` | `en,es,pt` | CSV de códigos ISO |
| `--channels` | `publications,broadcasting,programs` | CSV |
| `--out` | (stdout) | Path; crea padres |
| `--no-update` | `False` | No marca seen ni avanza `last_run` |
| `--json` | `False` | Emite envelope JSON en vez de markdown |

## Cron opcional

El toolkit **no** instala tareas automáticas. Si quieres digest semanal:

```cron
# Lunes 07:00 — digest a archivo
0 7 * * MON  /usr/local/bin/jw news digest --since last_run --out ~/Documents/jw-news/$(date +\%F).md
```

O con `systemd --user`:

```ini
# ~/.config/systemd/user/jw-news.timer
[Unit]
Description=Weekly JW news digest

[Timer]
OnCalendar=Mon 07:00
Persistent=true

[Install]
WantedBy=timers.target
```

```ini
# ~/.config/systemd/user/jw-news.service
[Unit]
Description=JW news digest

[Service]
Type=oneshot
ExecStart=/usr/local/bin/jw news digest --since last_run --out %h/Documents/jw-news/digest.md
```

## Tool MCP

Desde Claude Desktop / cualquier cliente MCP:

```
news_digest(since="last_run", languages=["en","es"], channels=["publications","programs"])
```

Devuelve un dict con `markdown` (ya formateado), `stats`, `findings` (con `citation.url` por item) y `warnings`.

## Estado local

- `~/.jw-agent-toolkit/news_seen.db` — SQLite con (channel, item_id, first_seen_at, last_seen_at). Override por env `JW_NEWS_SEEN_DB`.
- `~/.jw-agent-toolkit/cache.db` — caché HTTP de los clientes (compartido con el resto del toolkit).

Borra `news_seen.db` para resetear lo que ya viste (siguiente corrida tratará todo como nuevo).

## Troubleshooting

| Síntoma | Diagnóstico | Fix |
|---|---|---|
| Digest reporta cientos de items en la primera corrida | store vacío | Es lo esperado. Usa `--no-update` para inspeccionar o `--since 2026-05-30` para sellar la fecha como base. |
| Un `pub_code` da warning 404 | publicación descontinuada o pub_code antiguo en `seeds.py` | Sin acción; el warning es informativo. Audit anual de `seeds.py`. |
| `last_run` aparece como `None` | nunca corriste sin `--no-update` | Corre `jw news digest --since 2026-05-30` una vez. |
| Mismo día corrió 4 veces y satura la red | TTL del cache no se honra | Verifica que `DiskCache` no fue limpiada. Cache vive en `~/.jw-agent-toolkit/cache.db`. |
| `--since 2026-05-23` no filtra items "nuevos" | confusión esperada | `--since` afecta el header del digest. El diff real lo hace `news_seen.db`. |

## Política de privacidad

- Cero telemetría externa. Todo permanece en `~/.jw-agent-toolkit/`.
- El digest no contiene ningún dato personal — sólo metadata pública de jw.org.
```

- [ ] **Step 2: Link from `docs/README.md`**

Add to the "Guías por tema" list:

```markdown
- [Monitor de novedades](guias/monitor-de-novedades.md) — `jw news digest` detecta publicaciones, videos y workbooks nuevos. Local-first, determinista.
```

- [ ] **Step 3: Commit**

```bash
git add docs/guias/monitor-de-novedades.md docs/README.md
git commit -m "docs(news): user guide for jw news digest (Fase 25)"
```

---

### Task 13: Update VISION_AUDIT and ROADMAP

**Files:**
- Modify: `docs/VISION_AUDIT.md`
- Modify: `docs/ROADMAP.md`

- [ ] **Step 1: VISION_AUDIT row**

Append (above closing notes) to `docs/VISION_AUDIT.md`:

```markdown
| Fase 25 (news monitor) | ✅ Nuevo | `jw news digest` — 3 canales, seen-store SQLite, tool MCP |
```

- [ ] **Step 2: ROADMAP section**

Append to `docs/ROADMAP.md` after Fase 24:

```markdown
## Fase 25 — Monitor de novedades jw.org ✅

> Tier 2 alto valor recurrente. Spec: `docs/superpowers/specs/2026-05-30-fase-25-news-monitor-design.md`.

- ✅ Módulo nuevo `jw_core.news` (`models`, `store`, `sources`, `digest`, `seeds`).
- ✅ Tres `NewsSource`:
  - `PublicationsSource` — seed list × idiomas, periodical/non-periodical.
  - `BroadcastingSource` — `discover_all_videos` sobre `VideoOnDemand`.
  - `ProgramsSource` — `mwb`/`w` para [mes_actual, mes_actual+2).
- ✅ `SeenStore` SQLite en `~/.jw-agent-toolkit/news_seen.db` (`JW_NEWS_SEEN_DB`).
- ✅ Cache TTL: 6h (publications), 24h (broadcasting), 7d (programs).
- ✅ Diff `(new, retired)` + render markdown determinista byte-estable.
- ✅ Agente `news_monitor` (envuelve sources + store en AgentResult).
- ✅ CLI `jw news digest --since {last_run|epoch|ISO} --languages --channels --out --no-update --json`.
- ✅ Tool MCP `news_digest`.
- ✅ Guía `docs/guias/monitor-de-novedades.md` (incluye cron + systemd timers de ejemplo).
- ✅ 1 case L1 nuevo en `jw-eval` (`news_monitor_digest_en`).

### Cobertura de tests

- ✅ ~20 tests nuevos (`test_news_models.py`, `test_news_store.py`, `test_news_sources.py`, `test_news_digest.py`, `test_news_monitor.py`, `test_news_cli.py`).
- ✅ Suite global sin regresiones.
```

- [ ] **Step 3: Commit**

```bash
git add docs/VISION_AUDIT.md docs/ROADMAP.md
git commit -m "docs(roadmap): land Fase 25 — news monitor"
```

---

### Task 14: Final audit + execution choice

**Files:** none (verification only).

- [ ] **Step 1: Full suite green**

Run: `uv run pytest packages/ --tb=short -q`
Expected: all green; new tests counted.

- [ ] **Step 2: End-to-end CLI dry run (no network if cache is warm)**

Pre-condition: run `jw download fg --lang E --format EPUB --out /tmp` once to warm `~/.jw-agent-toolkit/cache.db`. Then:

```bash
uv run jw news digest --since epoch --languages en --channels publications --no-update
```

Expected: markdown digest printed; exit code 0.

- [ ] **Step 3: Verify the MCP tool count**

```bash
uv run python -c "from jw_mcp.server import mcp; print(len(list(mcp._tools)))"
```
Expected: one greater than before Fase 25.

- [ ] **Step 4: Verify store survives a roundtrip**

```bash
uv run jw news digest --since epoch --languages en --channels programs --out /tmp/d1.md
uv run jw news digest --since last_run --languages en --channels programs --out /tmp/d2.md
diff <(grep -v Generado /tmp/d1.md) <(grep -v Generado /tmp/d2.md) | head
```
Expected: the second digest reports `Nuevos: 0` because everything was marked seen.

- [ ] **Step 5: Cleanup the in-progress task**

Mark Fase 25 task as completed in the TaskList.

---

## Self-review summary

- **Spec coverage**: every section of the spec maps to a task:
  - Modelos → Task 1.
  - SeenStore → Task 2.
  - Seeds → Task 3.
  - Three sources → Task 4.
  - Diff + render → Task 5.
  - Package surface → Task 6.
  - Agent wrapper → Task 7.
  - CLI → Task 8.
  - MCP tool → Task 9.
  - Eval golden case → Task 10.
  - Regression check → Task 11.
  - Guía + cron snippet → Task 12.
  - ROADMAP + VISION_AUDIT audit → Task 13.
  - Final audit → Task 14.
- **No placeholders**: every code block has concrete code; every YAML has concrete fields; every command shows the exact invocation and expected output.
- **No LLM in critical path**: source `fetch`, store I/O, diff and markdown render are all sync deterministic CPU code (asyncio is only used to fan out network I/O concurrently in sources).
- **No network in tests**: every test uses stub clients or stub sources via dependency injection (`PublicationsSource(client=stub)`, `BroadcastingSource(client=stub)`, `news_monitor(sources=[stub])`, CLI test patches the agent function).
- **Determinism**: tests assert byte-stable markdown via reverse-order item input; seen-store roundtrip is checked; `mark_seen` preserves `first_seen_at`.
- **Type consistency**: `NewsItem.channel` is `Literal["publications","broadcasting","programs"]` from `models.py` and referenced in `seeds.py`, `sources.py`, `digest.py` and `news_monitor.py`. `since: str | None` consistent across CLI, agent, MCP tool. `update: bool` consistent.
- **Citations always present**: every `NewsItem.url` is mandatory (Pydantic field, no default), and the agent maps it to `Citation.url` for every `Finding`.
- **Honors no-daemon rule**: only one `asyncio.run` invocation per CLI call; no background threads; cron is documentation, not shipped.

## Execution choice

Plan completo. Dos opciones:

1. **Subagent-driven (recomendado)** — dispatch un sub-agente fresh por tarea, review entre tareas, iteración rápida (`superpowers:subagent-driven-development`). Especialmente útil aquí porque las tareas 1-6 son cleanly secuenciales y 7-9 paralelizables.
2. **Inline** — ejecuto tareas en esta sesión con checkpoints (`superpowers:executing-plans`).

¿Cuál prefieres?
