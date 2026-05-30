"""Tests for the EventStore JSONL tailer."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from jw_finetune.monitor.store import EventStore, synthesize_event


@pytest.mark.asyncio
async def test_synthesize_event_basics() -> None:
    ev = synthesize_event("step", loss=0.5, step=1)
    assert ev["kind"] == "step"
    assert ev["loss"] == 0.5
    assert "ts" in ev


@pytest.mark.asyncio
async def test_event_store_reads_existing_file(tmp_path: Path) -> None:
    events_path = tmp_path / "events.jsonl"
    events_path.write_text(
        json.dumps({"kind": "step", "step": 1, "loss": 1.5}) + "\n"
        + json.dumps({"kind": "step", "step": 2, "loss": 1.3}) + "\n",
        encoding="utf-8",
    )
    store = EventStore(events_path)
    store.start()
    await asyncio.sleep(0.7)  # let tail loop run

    assert len(store.buffer) == 2
    assert store.latest_loss() == pytest.approx(1.3)
    await store.stop()


@pytest.mark.asyncio
async def test_event_store_picks_up_appends(tmp_path: Path) -> None:
    events_path = tmp_path / "events.jsonl"
    events_path.write_text("", encoding="utf-8")
    store = EventStore(events_path)
    store.start()
    await asyncio.sleep(0.6)

    with events_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"kind": "log", "loss": 0.9}) + "\n")
        f.flush()

    await asyncio.sleep(0.8)
    assert any(ev.get("loss") == 0.9 for ev in store.buffer)
    await store.stop()


@pytest.mark.asyncio
async def test_event_store_subscribe_replays_buffer(tmp_path: Path) -> None:
    events_path = tmp_path / "events.jsonl"
    events_path.write_text(
        json.dumps({"kind": "step", "step": 1, "loss": 2.0}) + "\n",
        encoding="utf-8",
    )
    store = EventStore(events_path)
    store.start()
    await asyncio.sleep(0.7)

    sub_iter = store.subscribe().__aiter__()
    first = await asyncio.wait_for(sub_iter.__anext__(), timeout=2)
    assert first["loss"] == 2.0
    await store.stop()


@pytest.mark.asyncio
async def test_event_store_handles_malformed_lines(tmp_path: Path) -> None:
    events_path = tmp_path / "events.jsonl"
    events_path.write_text(
        "not-json\n"
        + json.dumps({"kind": "step", "loss": 0.5}) + "\n",
        encoding="utf-8",
    )
    store = EventStore(events_path)
    store.start()
    await asyncio.sleep(0.7)
    assert len(store.buffer) == 1  # malformed line skipped
    assert store.latest_loss() == 0.5
    await store.stop()


@pytest.mark.asyncio
async def test_event_store_missing_file_does_not_crash(tmp_path: Path) -> None:
    store = EventStore(tmp_path / "missing.jsonl")
    store.start()
    await asyncio.sleep(0.6)
    assert len(store.buffer) == 0
    await store.stop()
