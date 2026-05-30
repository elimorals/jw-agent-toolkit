"""Tests for retry/backoff."""

from __future__ import annotations

import pytest

from jw_finetune.synth.retry import retry_with_backoff


def test_retry_succeeds_first_try() -> None:
    calls = []
    def f() -> int:
        calls.append(1)
        return 42
    assert retry_with_backoff(f, max_attempts=3) == 42
    assert len(calls) == 1


def test_retry_succeeds_after_failures(monkeypatch) -> None:
    monkeypatch.setattr("time.sleep", lambda _x: None)
    attempts = [0]
    def f() -> str:
        attempts[0] += 1
        if attempts[0] < 3:
            raise ConnectionError("transient")
        return "ok"
    assert retry_with_backoff(f, max_attempts=5, initial_delay=0.01) == "ok"
    assert attempts[0] == 3


def test_retry_exhausts_and_raises(monkeypatch) -> None:
    monkeypatch.setattr("time.sleep", lambda _x: None)
    def f() -> None:
        raise ConnectionError("always")
    with pytest.raises(ConnectionError):
        retry_with_backoff(f, max_attempts=3, initial_delay=0.01)


def test_retry_does_not_retry_unmatched_exception(monkeypatch) -> None:
    monkeypatch.setattr("time.sleep", lambda _x: None)
    calls = [0]
    def f() -> None:
        calls[0] += 1
        raise ValueError("hard")
    with pytest.raises(ValueError):
        retry_with_backoff(f, max_attempts=5, retry_on=(ConnectionError,))
    assert calls[0] == 1  # no retries


def test_retry_with_jitter_disabled_uses_deterministic_delay(monkeypatch) -> None:
    sleeps = []
    monkeypatch.setattr("time.sleep", lambda x: sleeps.append(x))
    def f() -> None:
        raise ConnectionError("x")
    with pytest.raises(ConnectionError):
        retry_with_backoff(
            f, max_attempts=4, initial_delay=1.0,
            backoff_factor=2.0, jitter=False,
        )
    assert sleeps == [1.0, 2.0, 4.0]  # 3 sleeps before the 4th (final) attempt
