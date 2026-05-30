"""EventStore — tails a JSONL events file and broadcasts new lines.

The training callback writes events.jsonl; this class polls the file for
new lines and pushes them to any number of subscribers (WebSocket
connections, in-memory buffers). The implementation is intentionally
file-based rather than process-based because training can run in any
subprocess (or even another host with a shared filesystem).

Concurrency model: a single background asyncio task does the tailing.
Subscribers are added/removed from a list under an asyncio.Lock.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from collections import deque
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class EventStore:
    """Tail a JSONL file and broadcast events to subscribers."""

    def __init__(self, events_path: Path, *, buffer_size: int = 1000) -> None:
        self.events_path = Path(events_path)
        self.buffer: deque[dict[str, Any]] = deque(maxlen=buffer_size)
        self._subs: list[asyncio.Queue[dict[str, Any]]] = []
        self._lock = asyncio.Lock()
        self._stop = asyncio.Event()
        self._task: asyncio.Task | None = None
        self._last_pos: int = 0

    def start(self) -> None:
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._run(), name="event-tail")

    async def stop(self) -> None:
        self._stop.set()
        if self._task is not None:
            try:
                await asyncio.wait_for(self._task, timeout=2)
            except asyncio.TimeoutError:
                self._task.cancel()

    async def subscribe(self) -> AsyncIterator[dict[str, Any]]:
        """Yield buffered + future events to one subscriber.

        Replays the buffer first so a late client sees recent history.
        """
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        async with self._lock:
            for ev in self.buffer:
                await queue.put(ev)
            self._subs.append(queue)
        try:
            while not self._stop.is_set():
                ev = await queue.get()
                yield ev
        finally:
            async with self._lock:
                if queue in self._subs:
                    self._subs.remove(queue)

    async def _broadcast(self, ev: dict[str, Any]) -> None:
        self.buffer.append(ev)
        async with self._lock:
            for q in self._subs:
                try:
                    q.put_nowait(ev)
                except asyncio.QueueFull:
                    pass

    async def _run(self) -> None:
        """Poll the events file every 0.5s and broadcast new lines."""
        while not self._stop.is_set():
            try:
                if self.events_path.exists():
                    await self._read_new_lines()
            except Exception as e:  # noqa: BLE001
                logger.warning("EventStore tail error: %s", e)
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=0.5)
            except asyncio.TimeoutError:
                pass

    async def _read_new_lines(self) -> None:
        size = self.events_path.stat().st_size
        if size < self._last_pos:
            # File rotated/truncated — restart from 0.
            self._last_pos = 0
        if size == self._last_pos:
            return
        with self.events_path.open("r", encoding="utf-8") as f:
            f.seek(self._last_pos)
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    ev = json.loads(line)
                except json.JSONDecodeError:
                    continue
                await self._broadcast(ev)
            self._last_pos = f.tell()

    def latest_loss(self) -> float | None:
        """Convenience: most recent `loss` value in the buffer, if any."""
        for ev in reversed(self.buffer):
            if isinstance(ev, dict) and "loss" in ev:
                try:
                    return float(ev["loss"])
                except (TypeError, ValueError):
                    continue
        return None


def synthesize_event(kind: str, **fields: Any) -> dict[str, Any]:
    """Build an event dict with the timestamp fields the callback uses."""
    ev: dict[str, Any] = {"kind": kind, "ts": time.time(), **fields}
    return ev
