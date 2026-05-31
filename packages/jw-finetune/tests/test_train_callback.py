"""Tests for the JWMonitorCallback event log."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from jw_finetune.train.callback import JWMonitorCallback


def _read_events(p: Path) -> list[dict]:
    return [json.loads(ln) for ln in p.read_text(encoding="utf-8").splitlines() if ln]


def test_callback_creates_workspace(tmp_path: Path) -> None:
    cb = JWMonitorCallback(tmp_path / "new" / "ws")
    assert (tmp_path / "new" / "ws").exists()
    assert cb.events_path.parent.exists()


def test_callback_on_log_writes_event(tmp_path: Path) -> None:
    cb = JWMonitorCallback(tmp_path)
    state = SimpleNamespace(global_step=5)
    cb.on_log(None, state, None, logs={"loss": 1.23, "lr": 2e-4})
    events = _read_events(cb.events_path)
    assert len(events) == 1
    assert events[0]["kind"] == "log"
    assert events[0]["step"] == 5
    assert events[0]["loss"] == 1.23


def test_callback_full_sequence(tmp_path: Path) -> None:
    cb = JWMonitorCallback(tmp_path)
    state = SimpleNamespace(global_step=0)
    cb.on_train_begin(None, state, None)
    state.global_step = 10
    cb.on_step_end(None, state, None, logs={"loss": 0.9})
    cb.on_log(None, state, None, logs={"loss": 0.85})
    cb.on_evaluate(None, state, None, metrics={"eval_loss": 0.7})
    cb.on_save(None, state, None)
    state.global_step = 20
    cb.on_train_end(None, state, None)

    events = _read_events(cb.events_path)
    kinds = [e["kind"] for e in events]
    assert kinds == [
        "train_begin",
        "step",
        "log",
        "evaluate",
        "save",
        "train_end",
    ]
    # Each event has elapsed >= 0
    assert all(e["elapsed"] >= 0 for e in events)


def test_callback_handles_missing_state(tmp_path: Path) -> None:
    cb = JWMonitorCallback(tmp_path)
    cb.on_log(None, SimpleNamespace(), None, logs={"loss": 1.0})
    events = _read_events(cb.events_path)
    assert events[0]["step"] == -1  # default sentinel
