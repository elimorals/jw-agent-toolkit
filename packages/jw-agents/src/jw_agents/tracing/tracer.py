"""AgentTracer — the public API for emitting trace events.

Usage:
    tr = AgentTracer(agent="apologetics", store=JsonlTraceStore(path))
    with tr.run(input_kwargs={"question": q}, language="en"):
        with tr.step("topic_index_lookup", input_digest={"q_len": len(q)}) as step:
            for hit in hits:
                if keep(hit):
                    tr.kept(source="topic_index", citation_url=hit.url, reason="ok")
                else:
                    tr.dropped(source="topic_index", reason="low_score", score=hit.score)
            step.note_hits(len(hits))

Use `get_active_tracer()` instead of constructing one when you only need to
read the ambient tracer (e.g. from inside a sub-helper).
"""

from __future__ import annotations

import time
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Iterator
from uuid import UUID, uuid4

from jw_agents.tracing.schema import (
    FindingDroppedEvent,
    FindingKeptEvent,
    StepEndEvent,
    StepStartEvent,
    Trace,
    WarningEvent,
)
from jw_agents.tracing.store import NullTraceStore, TraceStore


def _now() -> datetime:
    return datetime.now(timezone.utc)


class _StepHandle:
    """Per-step counters surfaced to user code.

    Methods are intentionally tiny so the JIT can inline them.
    """

    __slots__ = ("_hits", "_kept", "_dropped")

    def __init__(self) -> None:
        self._hits: int | None = None
        self._kept: int | None = None
        self._dropped: int | None = None

    def note_hits(self, n: int) -> None:
        self._hits = n

    def note_kept(self, n: int) -> None:
        self._kept = n

    def note_dropped(self, n: int) -> None:
        self._dropped = n


class AgentTracer:
    """Holds the active store + monotonic counter, exposes step / kept / dropped."""

    def __init__(self, *, agent: str, store: TraceStore | None = None) -> None:
        self.agent = agent
        self.store: TraceStore = store if store is not None else NullTraceStore()
        self.trace_id: UUID = uuid4()
        self._seq: int = 0
        self._step_stack: list[str] = []
        self._kept_total: int = 0
        self._dropped_total: int = 0
        self._warnings_total: int = 0
        self._started: datetime | None = None
        self._started_perf: float | None = None
        self._language: str | None = None
        self._input: dict[str, Any] = {}

    @contextmanager
    def run(
        self,
        *,
        input_kwargs: dict[str, Any],
        language: str | None = None,
    ) -> Iterator["AgentTracer"]:
        """Bind run-level metadata, emit envelope on exit."""

        self._started = _now()
        self._started_perf = time.perf_counter()
        self._language = language
        self._input = dict(input_kwargs)
        try:
            yield self
        finally:
            finished = _now()
            duration_ms = int(
                (time.perf_counter() - (self._started_perf or 0.0)) * 1000
            )
            store_path = getattr(self.store, "_path", None)
            envelope = Trace(
                trace_id=self.trace_id,
                agent=self.agent,
                language=self._language,
                started_at=self._started or finished,
                finished_at=finished,
                duration_ms=duration_ms,
                input=self._input,
                findings_in=self._kept_total + self._dropped_total,
                findings_out=self._kept_total,
                warnings_count=self._warnings_total,
                events_path=str(store_path) if store_path else "",
            )
            self.store.complete(envelope)
            self.store.close()

    @contextmanager
    def step(
        self,
        name: str,
        *,
        input_digest: dict[str, Any] | None = None,
    ) -> Iterator[_StepHandle]:
        start_evt = StepStartEvent(
            ts=_now(),
            seq=self._next_seq(),
            name=name,
            input_digest=input_digest,
        )
        self.store.append(start_evt)
        self._step_stack.append(name)
        handle = _StepHandle()
        t0 = time.perf_counter()
        error: str | None = None
        try:
            yield handle
        except BaseException as exc:
            error = f"{type(exc).__name__}: {exc}"
            raise
        finally:
            duration_ms = int((time.perf_counter() - t0) * 1000)
            end_evt = StepEndEvent(
                ts=_now(),
                seq=self._next_seq(),
                name=name,
                duration_ms=duration_ms,
                hits=handle._hits,
                kept=handle._kept,
                dropped=handle._dropped,
                error=error,
            )
            self.store.append(end_evt)
            self._step_stack.pop()

    def kept(
        self,
        *,
        source: str,
        citation_url: str,
        score: float | None = None,
        rank: int | None = None,
        reason: str = "",
    ) -> None:
        self.store.append(
            FindingKeptEvent(
                ts=_now(),
                seq=self._next_seq(),
                source=source,
                citation_url=citation_url,
                score=score,
                rank=rank,
                reason=reason,
            )
        )
        self._kept_total += 1

    def dropped(
        self,
        *,
        source: str,
        reason: str,
        citation_url: str | None = None,
        score: float | None = None,
    ) -> None:
        self.store.append(
            FindingDroppedEvent(
                ts=_now(),
                seq=self._next_seq(),
                source=source,
                citation_url=citation_url,
                reason=reason,
                score=score,
            )
        )
        self._dropped_total += 1

    def warn(self, message: str, *, step: str | None = None) -> None:
        self.store.append(
            WarningEvent(
                ts=_now(),
                seq=self._next_seq(),
                message=message,
                step=step or (self._step_stack[-1] if self._step_stack else None),
            )
        )
        self._warnings_total += 1

    def _next_seq(self) -> int:
        s = self._seq
        self._seq = s + 1
        return s
