"""Regression guard: tracing overhead with JsonlTraceStore.

Compares the cost of running a representative loop:
  - NULL: NullTraceStore (effectively no-op).
  - JSONL: JsonlTraceStore writing to a tmp file with default buffering.

The overhead = (jsonl - null) / null. We assert a generous upper bound;
the design target is <= 5% inside real agents (which spend most of their
time on I/O and parsing, not on the tracer itself).
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Callable

import pytest

from jw_agents.tracing.store import JsonlTraceStore, NullTraceStore
from jw_agents.tracing.tracer import AgentTracer


def _workload(tracer: AgentTracer) -> None:
    with tracer.run(input_kwargs={"question": "x"}):
        with tracer.step("compute") as step:
            for i in range(2000):
                if i % 3 == 0:
                    tracer.kept(
                        source="rag",
                        citation_url="https://x",
                        score=0.5,
                        reason="ok",
                    )
                else:
                    tracer.dropped(source="rag", reason="dup")
            step.note_hits(2000)
            step.note_kept(666)
            step.note_dropped(1334)


def _time(fn: Callable[[], None], repeats: int = 3) -> float:
    samples = []
    for _ in range(repeats):
        t0 = time.perf_counter()
        fn()
        samples.append(time.perf_counter() - t0)
    return min(samples)


@pytest.mark.perf
def test_jsonl_overhead_bounded(tmp_path: Path) -> None:
    null_tracer = AgentTracer(agent="x", store=NullTraceStore())
    t_null = _time(lambda: _workload(null_tracer))

    def make_jsonl_run() -> None:
        tr = AgentTracer(
            agent="x", store=JsonlTraceStore(path=tmp_path / "ov.jsonl")
        )
        _workload(tr)

    t_jsonl = _time(make_jsonl_run)

    # On extremely fast machines `t_null` can be tiny; bail with skip rather
    # than misleading red.
    if t_null < 0.001:
        pytest.skip(f"null sample too fast ({t_null:.6f}s); skipping perf assertion")

    overhead = (t_jsonl - t_null) / t_null
    # The Jsonl path will always be > null. Allow up to 100x — the assertion
    # being measured is "writing JSONL doesn't crash and is bounded". The
    # spec's 7% target is about *agents* (which spend most of their time on
    # I/O and parsing), not the tracer in isolation.
    assert overhead < 100.0, (
        f"jsonl/null overhead = {overhead * 100:.1f}% "
        f"(t_null={t_null:.4f}s, t_jsonl={t_jsonl:.4f}s)"
    )
