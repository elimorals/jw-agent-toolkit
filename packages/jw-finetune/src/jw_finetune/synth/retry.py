"""Retry with exponential backoff for transient LLM provider failures.

Used by `OllamaProvider` and `AnthropicProvider` (wired in their generate
methods). We intentionally don't take a hard dependency on `tenacity` —
a tiny hand-rolled retry is fine for our needs and one less dep.
"""

from __future__ import annotations

import logging
import random
import time
from collections.abc import Callable
from typing import TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


def retry_with_backoff(
    fn: Callable[[], T],
    *,
    max_attempts: int = 4,
    initial_delay: float = 1.0,
    max_delay: float = 30.0,
    backoff_factor: float = 2.0,
    jitter: bool = True,
    retry_on: tuple[type[BaseException], ...] = (Exception,),
    label: str = "call",
) -> T:
    """Retry `fn` up to `max_attempts` times with exponential backoff.

    Exceptions matching `retry_on` are retried; anything else propagates
    immediately. The final exception (after all attempts fail) is raised.
    """
    last_exc: BaseException | None = None
    delay = initial_delay
    for attempt in range(1, max_attempts + 1):
        try:
            return fn()
        except retry_on as e:
            last_exc = e
            if attempt == max_attempts:
                logger.error("%s failed after %d attempts: %s", label, attempt, e)
                raise
            sleep_for = delay
            if jitter:
                sleep_for *= 0.5 + random.random()
            sleep_for = min(sleep_for, max_delay)
            logger.warning(
                "%s attempt %d/%d failed (%s); retrying in %.1fs",
                label,
                attempt,
                max_attempts,
                e,
                sleep_for,
            )
            time.sleep(sleep_for)
            delay = min(delay * backoff_factor, max_delay)
    # Unreachable but appeases type checkers
    if last_exc:
        raise last_exc
    raise RuntimeError("retry_with_backoff: unreachable")
