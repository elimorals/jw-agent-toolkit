"""Per-host token bucket rate limiter + exponential backoff with jitter.

Two pieces:

  - `TokenBucket`: async token bucket. Bounded refill rate and bucket size.
    Callers `await bucket.acquire(n=1)` before sending a request; the call
    sleeps just long enough to respect the configured rate.

  - `backoff_delay(attempt)`: exponential delay with full jitter. Use in
    retry loops on transient failures.

The HTTP clients in `jw_core.clients.*` can opt in to throttling by
passing a `Throttler` instance. By default they don't — light usage
doesn't need it. The constants here are conservative for `jw.org`
infrastructure (no public rate limit is documented, so we self-impose).
"""

from __future__ import annotations

import asyncio
import random
import time
from dataclasses import dataclass, field


@dataclass
class TokenBucket:
    """Classic token bucket. Refills `rate_per_sec` tokens per second.

    Default values target conservative jw.org usage: 2 requests/second
    with a burst of 5. Adjust per host if needed.
    """

    rate_per_sec: float = 2.0
    capacity: float = 5.0
    _tokens: float = field(init=False)
    _last_refill: float = field(init=False)
    _lock: asyncio.Lock = field(init=False)

    def __post_init__(self) -> None:
        self._tokens = self.capacity
        self._last_refill = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self, n: float = 1.0) -> None:
        """Block until `n` tokens are available, then consume them."""
        while True:
            async with self._lock:
                now = time.monotonic()
                elapsed = now - self._last_refill
                self._tokens = min(self.capacity, self._tokens + elapsed * self.rate_per_sec)
                self._last_refill = now
                if self._tokens >= n:
                    self._tokens -= n
                    return
                shortfall = n - self._tokens
                wait = shortfall / self.rate_per_sec
            await asyncio.sleep(wait)


class Throttler:
    """Per-host token buckets.

    Use one instance for the whole process; it lazily creates a bucket
    per host. Configure per-host limits via `set_limit(host, rate, capacity)`.
    """

    def __init__(self, default_rate: float = 2.0, default_capacity: float = 5.0) -> None:
        self.default_rate = default_rate
        self.default_capacity = default_capacity
        self._buckets: dict[str, TokenBucket] = {}
        self._per_host: dict[str, tuple[float, float]] = {}

    def set_limit(self, host: str, rate_per_sec: float, capacity: float) -> None:
        self._per_host[host] = (rate_per_sec, capacity)
        # Reset the bucket so the new settings take effect immediately.
        self._buckets.pop(host, None)

    def bucket_for(self, host: str) -> TokenBucket:
        if host not in self._buckets:
            rate, cap = self._per_host.get(host, (self.default_rate, self.default_capacity))
            self._buckets[host] = TokenBucket(rate_per_sec=rate, capacity=cap)
        return self._buckets[host]

    async def acquire(self, host: str, n: float = 1.0) -> None:
        await self.bucket_for(host).acquire(n)


def backoff_delay(attempt: int, *, base: float = 0.5, cap: float = 30.0) -> float:
    """Full-jitter exponential backoff. attempt 0 → returns small delay.

    Spec: AWS architecture blog `https://aws.amazon.com/blogs/architecture/exponential-backoff-and-jitter/`.

    Formula: random.uniform(0, min(cap, base * 2**attempt)).
    """
    upper = min(cap, base * (2**attempt))
    return random.uniform(0, upper)
