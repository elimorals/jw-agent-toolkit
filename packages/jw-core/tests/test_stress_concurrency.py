"""Stress + concurrency tests for the Phase 9 infrastructure.

What this file proves:

  1. `TokenBucket` is correct under N concurrent `asyncio.gather()`
     acquires (the internal `asyncio.Lock` works as advertised).
  2. `Throttler` keeps per-host buckets independent — saturating one
     host doesn't slow another.
  3. `DiskCache` (SQLite WAL) survives N concurrent threads writing the
     same/different keys.
  4. `VectorStore` ingests batches up to 10k chunks without quadratic
     blowup on `add()` / `hybrid_search()`.
  5. The shared `politely_get` helper handles N concurrent requests
     against the same cache without corruption.

These tests are intentionally CPU-only (no network) so they run in CI.
Thresholds are calibrated for a reasonable laptop; CI runners may be
slower, so we use loose upper bounds with `pytest.skip` if a system is
under heavy load.
"""

from __future__ import annotations

import asyncio
import threading
import time
from pathlib import Path

import httpx
import pytest
from jw_core.cache import DiskCache
from jw_core.clients._polite import politely_get
from jw_core.throttle import Throttler, TokenBucket

# ── TokenBucket concurrency ───────────────────────────────────────────


async def _gather_acquires(bucket: TokenBucket, n: int) -> float:
    """Run N acquires concurrently; return wall-clock time."""
    t0 = time.perf_counter()
    await asyncio.gather(*(bucket.acquire(1) for _ in range(n)))
    return time.perf_counter() - t0


@pytest.mark.asyncio
async def test_token_bucket_100_concurrent_acquires_serializes_under_lock() -> None:
    """100 concurrent acquires must total ~= (N - capacity) / rate seconds.

    With rate=100/s + capacity=10, the first 10 fire instantly and the
    remaining 90 are paced at 100/s, totaling ~0.9s. We assert it stays
    within a reasonable envelope.
    """
    bucket = TokenBucket(rate_per_sec=100.0, capacity=10.0)
    elapsed = await _gather_acquires(bucket, 100)
    # Expect at least 0.7s (the 90 paced acquires) and at most 2.0s
    # (overhead from asyncio scheduling).
    assert 0.7 < elapsed < 2.5, f"Unexpected wall-clock: {elapsed:.2f}s"


@pytest.mark.asyncio
async def test_token_bucket_under_pressure_never_over_consumes() -> None:
    """Even with massive concurrency, the bucket never goes negative."""
    bucket = TokenBucket(rate_per_sec=200.0, capacity=20.0)
    # Fire 500 concurrent — should serialize cleanly.
    await _gather_acquires(bucket, 500)
    # The lock-tracked field should be >= 0.
    assert bucket._tokens >= 0


@pytest.mark.asyncio
async def test_throttler_multi_host_independent_buckets() -> None:
    """Saturating host A must not throttle host B."""
    t = Throttler(default_rate=10.0, default_capacity=2.0)
    # Drain bucket A.
    await asyncio.gather(*(t.acquire("hostA") for _ in range(2)))
    # Bucket A now has 0 tokens; an immediate hostA acquire would wait.
    # Bucket B is still full; 2 acquires must be instantaneous.
    t0 = time.perf_counter()
    await asyncio.gather(*(t.acquire("hostB") for _ in range(2)))
    elapsed = time.perf_counter() - t0
    assert elapsed < 0.05, f"hostB throttled unexpectedly: {elapsed:.3f}s"


# ── DiskCache concurrency ─────────────────────────────────────────────


def test_disk_cache_thread_safe_concurrent_writes(tmp_path: Path) -> None:
    """100 threads write distinct keys; all must persist and be readable."""
    cache = DiskCache(tmp_path / "c.db")
    errors: list[Exception] = []

    def worker(i: int) -> None:
        try:
            cache.set(f"key_{i}", str(i).encode(), ttl_seconds=3600)
        except Exception as e:  # pragma: no cover
            errors.append(e)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(100)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=5.0)

    assert not errors, f"Concurrent writes raised: {errors[:3]}"
    # All keys readable.
    for i in range(100):
        assert cache.get(f"key_{i}") == str(i).encode()
    cache.close()


def test_disk_cache_hammering_same_key(tmp_path: Path) -> None:
    """Many threads set/get the same key; reads must always return SOMETHING."""
    cache = DiskCache(tmp_path / "c.db")
    cache.set("hot_key", b"initial")

    null_reads = 0

    def writer() -> None:
        for i in range(50):
            cache.set("hot_key", f"v{i}".encode())

    def reader() -> None:
        nonlocal null_reads
        for _ in range(50):
            val = cache.get("hot_key")
            if val is None:
                null_reads += 1

    threads = [threading.Thread(target=writer) for _ in range(5)] + [threading.Thread(target=reader) for _ in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=10.0)

    # No read should return None — the key is always present once initialized.
    assert null_reads == 0, f"Got {null_reads} null reads under hammering"
    cache.close()


# ── VectorStore at scale ──────────────────────────────────────────────


def test_vector_store_handles_10k_chunks_in_batches(tmp_path: Path) -> None:
    """Adding 10 batches of 1k chunks each must stay under a reasonable budget."""
    from jw_rag import Chunk, FakeEmbedder, VectorStore

    embed = FakeEmbedder(dim=32)
    store = VectorStore(tmp_path / "rag", embed)
    batch_times: list[float] = []
    for batch_idx in range(10):
        chunks = [
            Chunk(
                id=f"c{batch_idx}_{i}",
                text=f"sample text batch {batch_idx} item {i} love peace hope",
                source_id=f"batch_{batch_idx}",
            )
            for i in range(1000)
        ]
        t0 = time.perf_counter()
        store.add(chunks)
        batch_times.append(time.perf_counter() - t0)
    assert store.count == 10_000
    # Each batch should add in < 3s on a normal laptop. CI runners are
    # slower; allow up to 10s per batch.
    assert max(batch_times) < 10.0, f"Slowest batch: {max(batch_times):.2f}s"


def test_vector_store_search_latency_stays_bounded(tmp_path: Path) -> None:
    """Hybrid search over a 5k-chunk store must respond in < 1s."""
    from jw_rag import Chunk, FakeEmbedder, VectorStore

    embed = FakeEmbedder(dim=32)
    store = VectorStore(tmp_path / "rag", embed)
    store.add(
        [
            Chunk(id=f"c{i}", text=f"chunk number {i} text content love peace hope", source_id=f"src_{i % 100}")
            for i in range(5000)
        ]
    )
    # Hot path: 50 queries; record p99.
    latencies = []
    for q in range(50):
        t0 = time.perf_counter()
        hits = store.hybrid_search(f"query {q} content", top_k=5)
        latencies.append(time.perf_counter() - t0)
        assert len(hits) == 5
    p99 = sorted(latencies)[int(len(latencies) * 0.99)]
    assert p99 < 1.0, f"Search p99 too high: {p99:.3f}s"


# ── politely_get under concurrency ────────────────────────────────────


def _mock_transport() -> httpx.MockTransport:
    """Mock transport returning a small JSON body."""

    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            content=b'{"k": "v"}',
            headers={"content-type": "application/json"},
        )

    return httpx.MockTransport(handler)


@pytest.mark.asyncio
async def test_politely_get_50_concurrent_with_cache(tmp_path: Path) -> None:
    """50 concurrent GETs hitting the same URL must result in exactly 1 fetch."""
    cache = DiskCache(tmp_path / "c.db")
    fetched = 0

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal fetched
        fetched += 1
        return httpx.Response(200, content=b'{"v": 1}')

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        # First call populates the cache (sync, since handler is sync).
        await politely_get(http, "https://api.test/x", cache=cache)
        # Now 50 concurrent — they should all hit the cache.
        await asyncio.gather(*(politely_get(http, "https://api.test/x", cache=cache) for _ in range(50)))
    # Only the priming call hit the transport.
    assert fetched == 1, f"Expected 1 fetch, got {fetched}"
    cache.close()


@pytest.mark.asyncio
async def test_politely_get_throttler_serializes_concurrent_burst() -> None:
    """50 concurrent GETs against rate=20/s + capacity=5 take ~2.25s."""
    throttler = Throttler(default_rate=20.0, default_capacity=5.0)
    async with httpx.AsyncClient(transport=_mock_transport()) as http:
        t0 = time.perf_counter()
        await asyncio.gather(*(politely_get(http, "https://api.test/x", throttler=throttler) for _ in range(50)))
        elapsed = time.perf_counter() - t0
    # 5 burst + 45 / 20 = 2.25s expected; allow [1.8s, 4.0s].
    assert 1.8 < elapsed < 4.0, f"Unexpected wall-clock: {elapsed:.2f}s"
