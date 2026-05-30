"""Property-based tests with Hypothesis.

These differ from example-based tests by generating *random valid
inputs* and checking that universal invariants hold. Hypothesis
shrinks failures to a minimal reproducer.

What we fuzz:

  1. **Reference parser** — for any known book + chapter + verse triple,
     the parser must reconstruct the correct BibleRef.
  2. **DiskCache** — any (key, value) pair roundtrips faithfully.
  3. **TokenBucket** — for any positive rate/capacity, `_tokens` never
     goes negative after N concurrent acquires.
  4. **Reference parser does not crash** on arbitrary noisy text.

Hypothesis is configured with default settings; runtime is bounded.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from hypothesis import HealthCheck, assume, given, settings
from hypothesis import strategies as st
from jw_core.cache import DiskCache
from jw_core.data.books import BOOKS
from jw_core.parsers.reference import parse_all_references, parse_reference
from jw_core.throttle import TokenBucket

# ── Reference parser fuzzing ──────────────────────────────────────────


# A list of (book_num, primary_name) tuples to sample from.
_BOOK_SAMPLES = [(b["num"], b["names"]["en"][0]) for b in BOOKS]


@given(
    book=st.sampled_from(_BOOK_SAMPLES),
    chapter=st.integers(min_value=1, max_value=150),
    verse_start=st.integers(min_value=1, max_value=176),
)
@settings(max_examples=100, deadline=2000)
def test_reference_parser_roundtrips_known_book_names(book: tuple[int, str], chapter: int, verse_start: int) -> None:
    """Any `{book_name} {chapter}:{verse}` constructed from the registry
    must parse back to the same book_num + chapter + verse_start."""
    book_num, book_name = book
    ref_str = f"{book_name} {chapter}:{verse_start}"
    ref = parse_reference(ref_str)
    assert ref is not None, f"parser returned None for valid input: {ref_str!r}"
    assert ref.book_num == book_num
    assert ref.chapter == chapter
    assert ref.verse_start == verse_start


@given(
    book=st.sampled_from(_BOOK_SAMPLES),
    chapter=st.integers(min_value=1, max_value=150),
    v_start=st.integers(min_value=1, max_value=100),
    v_end=st.integers(min_value=1, max_value=100),
)
@settings(max_examples=50, deadline=2000)
def test_reference_parser_handles_arbitrary_verse_ranges(
    book: tuple[int, str], chapter: int, v_start: int, v_end: int
) -> None:
    assume(v_end >= v_start)
    book_num, book_name = book
    ref_str = f"{book_name} {chapter}:{v_start}-{v_end}"
    ref = parse_reference(ref_str)
    assert ref is not None
    assert ref.book_num == book_num
    assert ref.verse_start == v_start
    assert ref.verse_end == v_end


@given(noise=st.text(alphabet=st.characters(blacklist_categories=("Cs",)), max_size=200))
@settings(max_examples=100, deadline=2000, suppress_health_check=[HealthCheck.too_slow])
def test_reference_parser_never_crashes_on_arbitrary_text(noise: str) -> None:
    """For any noisy text, parse_all_references either returns refs or [],
    but never raises."""
    refs = parse_all_references(noise)
    # All returned refs must have valid structure.
    for r in refs:
        assert 1 <= r.book_num <= 66
        assert r.chapter >= 1


@given(
    spanish_book=st.sampled_from(
        [
            ("Juan", 43),
            ("Génesis", 1),
            ("Romanos", 45),
            ("1 Corintios", 46),
            ("Apocalipsis", 66),
            ("Salmos", 19),
            ("Hebreos", 58),
        ]
    ),
    chapter=st.integers(min_value=1, max_value=150),
    verse=st.integers(min_value=1, max_value=100),
)
@settings(max_examples=50, deadline=2000)
def test_reference_parser_spanish_names(spanish_book: tuple[str, int], chapter: int, verse: int) -> None:
    name, expected_num = spanish_book
    ref = parse_reference(f"{name} {chapter}:{verse}")
    assert ref is not None
    assert ref.book_num == expected_num
    assert ref.chapter == chapter
    assert ref.verse_start == verse


# ── DiskCache fuzzing ─────────────────────────────────────────────────


@given(
    key=st.text(
        min_size=1,
        max_size=200,
        alphabet=st.characters(
            blacklist_categories=("Cs", "Cc"),  # surrogates + control chars
        ),
    ),
    value=st.binary(min_size=0, max_size=10_000),
)
@settings(max_examples=50, deadline=2000, suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_disk_cache_roundtrip_arbitrary_bytes(tmp_path: Path, key: str, value: bytes) -> None:
    """Any (key, value) the user provides must roundtrip."""
    cache = DiskCache(tmp_path / "fuzz.db")
    try:
        cache.set(key, value)
        assert cache.get(key) == value
    finally:
        cache.close()


@given(
    keys_values=st.lists(
        st.tuples(
            st.text(
                min_size=1,
                max_size=50,
                alphabet=st.characters(
                    blacklist_categories=("Cs", "Cc"),
                ),
            ),
            st.binary(min_size=0, max_size=500),
        ),
        min_size=1,
        max_size=20,
        unique_by=lambda kv: kv[0],
    ),
)
@settings(max_examples=30, deadline=3000, suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_disk_cache_handles_batch_writes_then_reads(tmp_path: Path, keys_values: list[tuple[str, bytes]]) -> None:
    """A batch of unique-key writes must all be readable afterwards.

    `tmp_path` is reused across hypothesis examples (function-scoped
    fixture). We `.clear()` at the start so each example sees a fresh
    cache; otherwise stats counts entries from previous iterations.
    """
    cache = DiskCache(tmp_path / "fuzz.db")
    try:
        cache.clear()
        for k, v in keys_values:
            cache.set(k, v)
        for k, v in keys_values:
            assert cache.get(k) == v
        assert cache.stats()["total"] == len(keys_values)
    finally:
        cache.close()


# ── TokenBucket fuzzing ──────────────────────────────────────────────


@given(
    # Keep the rate fast enough that any combination finishes quickly:
    # worst case is (n_concurrent - capacity) / rate seconds, and we bound
    # n_concurrent so this stays well under 1s.
    rate=st.floats(min_value=20.0, max_value=1000.0, allow_nan=False, allow_infinity=False),
    capacity=st.floats(min_value=1.0, max_value=100.0, allow_nan=False, allow_infinity=False),
    n_concurrent=st.integers(min_value=1, max_value=10),
)
@settings(max_examples=20, deadline=None)
def test_token_bucket_never_goes_negative_under_concurrency(
    rate: float, capacity: float, n_concurrent: int
) -> None:
    """For ANY rate + capacity, after N concurrent acquires, _tokens >= 0.

    The invariant we're fuzzing is the lock + accounting correctness — NOT
    timing. Hypothesis deadline disabled because rate/capacity combos
    fundamentally vary in wall-clock cost.
    """
    bucket = TokenBucket(rate_per_sec=rate, capacity=capacity)

    async def run() -> None:
        await asyncio.gather(*(bucket.acquire(1) for _ in range(n_concurrent)))

    asyncio.run(run())
    assert bucket._tokens >= 0, f"Token bucket went negative: {bucket._tokens}"
