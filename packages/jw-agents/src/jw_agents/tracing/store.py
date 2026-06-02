"""TraceStore implementations.

  NullTraceStore     no-op. Default when --trace is absent. ZERO cost.
  InMemoryTraceStore retains events + envelope in memory; for tests.
  JsonlTraceStore    append-only writer to JSON Lines. Default when --trace.

The envelope is written as the FINAL line with `"type": "trace_complete"`
so consumers can detect partial traces (no envelope means the run crashed).
"""

from __future__ import annotations

import json
import sys
from io import BufferedWriter
from pathlib import Path
from typing import Protocol

from jw_agents.tracing.schema import Trace, TraceEvent


class TraceStore(Protocol):
    def append(self, event: TraceEvent) -> None: ...
    def complete(self, trace: Trace) -> None: ...
    def close(self) -> None: ...


class NullTraceStore:
    """Discards everything. Method body is `pass` for branch-predictor speed."""

    __slots__ = ()

    def append(self, event: TraceEvent) -> None:  # noqa: ARG002
        pass

    def complete(self, trace: Trace) -> None:  # noqa: ARG002
        pass

    def close(self) -> None:
        pass


class InMemoryTraceStore:
    """Test helper. Keeps every event + the envelope in memory."""

    def __init__(self) -> None:
        self.events: list[TraceEvent] = []
        self.envelope: Trace | None = None

    def append(self, event: TraceEvent) -> None:
        self.events.append(event)

    def complete(self, trace: Trace) -> None:
        self.envelope = trace

    def close(self) -> None:
        pass


class JsonlTraceStore:
    """Append-only JSON Lines writer.

    `path=None` writes to sys.stdout (used by `--trace -`).
    Parent dirs are created on demand. The writer is opened lazily on the
    first event so a NO-OP run produces no file.
    """

    def __init__(self, path: Path | None, *, buffer_size: int = 64) -> None:
        self._path = path
        self._buffer_size = buffer_size
        self._fh: BufferedWriter | None = None
        self._is_stdout = path is None

    def _ensure_open(self) -> None:
        if self._fh is not None:
            return
        if self._is_stdout:
            return
        assert self._path is not None
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._fh = self._path.open("ab", buffering=self._buffer_size * 256)

    def _write(self, line: str) -> None:
        if self._is_stdout:
            sys.stdout.write(line)
            return
        assert self._fh is not None
        self._fh.write(line.encode("utf-8"))

    def append(self, event: TraceEvent) -> None:
        self._ensure_open()
        self._write(event.model_dump_json() + "\n")

    def complete(self, trace: Trace) -> None:
        self._ensure_open()
        # The envelope is tagged with a synthetic type so tools can detect it.
        payload = json.loads(trace.model_dump_json())
        payload["type"] = "trace_complete"
        self._write(json.dumps(payload, ensure_ascii=False) + "\n")
        if self._is_stdout:
            sys.stdout.flush()
        else:
            assert self._fh is not None
            self._fh.flush()

    def close(self) -> None:
        if self._fh is not None and not self._is_stdout:
            self._fh.close()
        self._fh = None
