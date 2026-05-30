"""Tests for Phase 9: DiskCache, Throttler, Telemetry."""

import asyncio
import os
import time
from pathlib import Path

import pytest

from jw_core.cache import DiskCache
from jw_core.telemetry import Telemetry, _shape_hash
from jw_core.throttle import TokenBucket, Throttler, backoff_delay


# ── DiskCache ───────────────────────────────────────────────────────────

def test_cache_set_get_roundtrip(tmp_path: Path) -> None:
    with DiskCache(tmp_path / "c.db") as c:
        c.set("foo", b"hello")
        assert c.get("foo") == b"hello"


def test_cache_returns_none_for_missing(tmp_path: Path) -> None:
    with DiskCache(tmp_path / "c.db") as c:
        assert c.get("nope") is None


def test_cache_expires_after_ttl(tmp_path: Path) -> None:
    with DiskCache(tmp_path / "c.db") as c:
        c.set("k", b"v", ttl_seconds=0.01)
        time.sleep(0.05)
        assert c.get("k") is None  # TTL elapsed, lazy eviction


def test_cache_cleanup_returns_count(tmp_path: Path) -> None:
    with DiskCache(tmp_path / "c.db") as c:
        c.set("a", b"x", ttl_seconds=0.001)
        c.set("b", b"y", ttl_seconds=3600)
        time.sleep(0.05)
        deleted = c.cleanup_expired()
        assert deleted == 1
        assert c.get("b") == b"y"


def test_cache_stats(tmp_path: Path) -> None:
    with DiskCache(tmp_path / "c.db") as c:
        c.set("live", b"x")
        c.set("stale", b"y", ttl_seconds=0.001)
        time.sleep(0.05)
        s = c.stats()
        assert s["total"] == 2
        assert s["live"] == 1
        assert s["expired"] == 1


def test_cache_clear(tmp_path: Path) -> None:
    with DiskCache(tmp_path / "c.db") as c:
        c.set("a", b"x")
        c.clear()
        assert c.get("a") is None


# ── TokenBucket / Throttler ────────────────────────────────────────────

async def _consume(bucket: TokenBucket, n: int) -> float:
    """Consume n tokens; return wall-clock time taken."""
    t0 = time.monotonic()
    for _ in range(n):
        await bucket.acquire(1)
    return time.monotonic() - t0


def test_token_bucket_immediate_burst() -> None:
    """A fresh bucket with capacity=5 lets 5 acquires fire immediately."""
    bucket = TokenBucket(rate_per_sec=1.0, capacity=5.0)
    elapsed = asyncio.run(_consume(bucket, 5))
    assert elapsed < 0.05  # essentially instantaneous


def test_token_bucket_throttles_excess() -> None:
    """The 6th acquire on a capacity-5 bucket must wait for the next refill."""
    bucket = TokenBucket(rate_per_sec=10.0, capacity=5.0)  # 10/sec → 100ms each
    elapsed = asyncio.run(_consume(bucket, 6))
    # The 6th call needs ~100ms of refill (1 token / 10 per sec).
    assert elapsed > 0.08


def test_throttler_creates_bucket_per_host() -> None:
    t = Throttler()
    assert t.bucket_for("a") is not t.bucket_for("b")
    assert t.bucket_for("a") is t.bucket_for("a")


def test_throttler_set_limit_overrides_default() -> None:
    t = Throttler()
    t.set_limit("a", rate_per_sec=10.0, capacity=1.0)
    assert t.bucket_for("a").rate_per_sec == 10.0
    assert t.bucket_for("a").capacity == 1.0


def test_backoff_delay_bounded() -> None:
    """backoff_delay is bounded to `cap` regardless of attempt."""
    for attempt in range(20):
        d = backoff_delay(attempt, base=0.5, cap=2.0)
        assert 0 <= d <= 2.0


def test_backoff_delay_grows_with_attempt() -> None:
    """The cap window grows with attempt (statistically, mean grows too)."""
    import statistics
    early = [backoff_delay(0, base=0.5, cap=60) for _ in range(50)]
    late = [backoff_delay(4, base=0.5, cap=60) for _ in range(50)]
    assert statistics.mean(late) > statistics.mean(early)


# ── Telemetry ──────────────────────────────────────────────────────────

def test_shape_hash_same_shape_different_values() -> None:
    a = {"x": 1, "y": "hello"}
    b = {"x": 999, "y": "different"}
    assert _shape_hash(a) == _shape_hash(b)


def test_shape_hash_new_key_changes_hash() -> None:
    a = {"x": 1}
    b = {"x": 1, "y": 2}
    assert _shape_hash(a) != _shape_hash(b)


def test_shape_hash_nested_structure() -> None:
    a = {"results": [{"title": "x", "url": "y"}]}
    b = {"results": [{"title": "x", "url": "y", "snippet": "z"}]}
    # Sample of first element shows a new 'snippet' key → different hash.
    assert _shape_hash(a) != _shape_hash(b)


def test_telemetry_disabled_by_default(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("JW_TELEMETRY_ENABLED", raising=False)
    t = Telemetry(tmp_path / "tel.json")
    assert t.enabled is False
    assert t.record("anything", {"a": 1}) is False  # no-op


def test_telemetry_records_baseline(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("JW_TELEMETRY_ENABLED", "1")
    p = tmp_path / "tel.json"
    t = Telemetry(p)
    # First call learns the baseline; should NOT report drift.
    assert t.record("/api/x", {"a": 1, "b": "x"}) is False
    assert "/api/x" in t.report()["baselines"]


def test_telemetry_detects_drift(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("JW_TELEMETRY_ENABLED", "1")
    t = Telemetry(tmp_path / "tel.json")
    t.record("/api/x", {"a": 1, "b": "x"})
    # Second call with a new shape → drift.
    drift = t.record("/api/x", {"a": 1, "b": "x", "c": [1, 2]})
    assert drift is True
    assert len(t.report()["drift_events"]) == 1


def test_telemetry_persists_across_instances(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("JW_TELEMETRY_ENABLED", "1")
    p = tmp_path / "tel.json"
    t1 = Telemetry(p)
    t1.record("/api/y", {"foo": [1]})
    t2 = Telemetry(p)
    # Same baseline survives; second telemetry sees it.
    assert "/api/y" in t2.report()["baselines"]
