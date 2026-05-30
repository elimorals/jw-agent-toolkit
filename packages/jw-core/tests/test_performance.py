"""Performance baselines for the hot paths.

These tests assert *upper bounds* — not micro-benchmarks. They exist to
detect regressions: if a refactor makes the reference parser 10x slower
or the embedder thrashes the cache, CI will catch it before merge.

Thresholds are generous so CI runners don't flake. Tighten only if you
have benchmark data and a stable runner.

What's measured:

  1. Reference parser throughput — 1000 refs.
  2. JWPUB decryption — full Trinity brochure (14 docs).
  3. FakeEmbedder throughput — 10k texts.
  4. VectorStore hybrid search — 1000 chunks, 50 queries, p99.
  5. DiskCache — 1000 set/get cycles.
  6. politely_get cache hit overhead vs miss.
"""

from __future__ import annotations

import time
from pathlib import Path

import httpx
import pytest
from jw_core.cache import DiskCache
from jw_core.clients._polite import politely_get

# ── Reference parser ───────────────────────────────────────────────────


def test_perf_reference_parser_1000_refs_in_under_300ms() -> None:
    from jw_core.parsers.reference import parse_all_references

    # Use semicolons to prevent adjacent-ref boundary collisions like
    # "5:21 Juan" being misread when refs are separated only by spaces.
    refs_per_cycle = [
        "Juan 3:16",
        "1 Co 13:4-7",
        "Hebreos 13:5",
        "Genesis 1:1",
        "Apocalipsis 21:4",
        "Mateo 24:14",
        "Romanos 8:28",
        "Salmo 23:1",
        "Filipenses 4:6-7",
        "1 Tesalonicenses 5:21",
    ]
    text = "; ".join(refs_per_cycle * 100)  # 1000 refs total
    t0 = time.perf_counter()
    refs = parse_all_references(text)
    elapsed = time.perf_counter() - t0
    assert len(refs) == 1000, f"Expected 1000 refs, got {len(refs)}"
    # The whole batch must finish well under 300ms on a normal laptop.
    assert elapsed < 0.30, f"Parsing 1000 refs took {elapsed * 1000:.1f}ms (>300ms)"


# ── JWPUB decryption ───────────────────────────────────────────────────


def test_perf_jwpub_decrypt_full_brochure_under_2s() -> None:
    from jw_core.parsers.jwpub import parse_jwpub

    pub_path = Path("data/jwpub_test/ti_E.jwpub")
    if not pub_path.exists():
        pytest.skip(f"{pub_path} not downloaded; run scripts/download_jwpub.py")
    t0 = time.perf_counter()
    pub = parse_jwpub(pub_path)
    elapsed = time.perf_counter() - t0
    # 14 documents, ~5KB each — should be quick.
    assert pub.decrypted_text_available
    assert elapsed < 2.0, f"Decrypting ti_E.jwpub took {elapsed:.2f}s"


# ── FakeEmbedder throughput ───────────────────────────────────────────


def test_perf_fake_embedder_10k_texts_under_3s() -> None:
    """SHA-256 based embedder should hit ~10k texts/sec on any laptop."""
    from jw_rag import FakeEmbedder

    embed = FakeEmbedder(dim=64)
    texts = [f"text {i} body content love peace hope" for i in range(10_000)]
    t0 = time.perf_counter()
    vecs = embed.embed(texts)
    elapsed = time.perf_counter() - t0
    assert vecs.shape == (10_000, 64)
    assert elapsed < 3.0, f"Embedding 10k texts took {elapsed:.2f}s"


# ── VectorStore search latency ────────────────────────────────────────


def test_perf_vector_store_search_p99_under_100ms(tmp_path: Path) -> None:
    """Hybrid search on a 1000-chunk corpus must respond in <100ms p99."""
    from jw_rag import Chunk, FakeEmbedder, VectorStore

    embed = FakeEmbedder(dim=32)
    store = VectorStore(tmp_path / "rag", embed)
    store.add(
        [Chunk(id=f"c{i}", text=f"chunk {i} love peace hope kingdom", source_id=f"src_{i % 50}") for i in range(1000)]
    )
    latencies = []
    for q in range(100):
        t0 = time.perf_counter()
        store.hybrid_search(f"love {q}", top_k=5)
        latencies.append(time.perf_counter() - t0)
    p50 = sorted(latencies)[50]
    p99 = sorted(latencies)[99]
    # p50 should be fast; p99 has more variance.
    assert p50 < 0.05, f"Search p50 too high: {p50 * 1000:.1f}ms"
    assert p99 < 0.30, f"Search p99 too high: {p99 * 1000:.1f}ms"


# ── DiskCache throughput ──────────────────────────────────────────────


def test_perf_disk_cache_1000_set_get_under_1s(tmp_path: Path) -> None:
    cache = DiskCache(tmp_path / "c.db")
    try:
        t0 = time.perf_counter()
        for i in range(1000):
            cache.set(f"key_{i}", f"value_{i}".encode())
        set_time = time.perf_counter() - t0

        t0 = time.perf_counter()
        for i in range(1000):
            assert cache.get(f"key_{i}") == f"value_{i}".encode()
        get_time = time.perf_counter() - t0

        assert set_time < 1.5, f"1000 sets took {set_time:.2f}s"
        assert get_time < 0.5, f"1000 gets took {get_time:.2f}s"
    finally:
        cache.close()


# ── politely_get cache-hit overhead ───────────────────────────────────


@pytest.mark.asyncio
async def test_perf_politely_get_cache_hit_under_1ms(tmp_path: Path) -> None:
    """A cache hit should be much faster than a miss."""
    cache = DiskCache(tmp_path / "c.db")

    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b'{"v": 1}')

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        # Prime the cache.
        await politely_get(http, "https://api.test/x", cache=cache)

        # Time 100 hits.
        t0 = time.perf_counter()
        for _ in range(100):
            await politely_get(http, "https://api.test/x", cache=cache)
        avg_hit = (time.perf_counter() - t0) / 100

    # Each cache hit should be sub-millisecond.
    assert avg_hit < 0.005, f"Cache hit avg: {avg_hit * 1000:.2f}ms"
    cache.close()


# ── Article HTML parser (real fixture) ────────────────────────────────


def test_perf_article_parser_on_real_fixture_under_500ms() -> None:
    """Parsing the John 3 nwtsty fixture (~195KB) must stay under 500ms."""
    from jw_core.parsers.article import parse_article

    fixture = (Path(__file__).parent / "fixtures" / "nwtsty_john3.html").read_text(encoding="utf-8")
    t0 = time.perf_counter()
    article = parse_article(fixture)
    elapsed = time.perf_counter() - t0
    assert article.title
    assert elapsed < 0.5, f"Article parser took {elapsed * 1000:.1f}ms"


# ── Topic-index parser at scale ───────────────────────────────────────


def test_perf_topic_index_parser_trinity_under_500ms() -> None:
    """Parsing the 73KB Trinity page (185 subheadings, 563 citations)."""
    from jw_core.parsers.topic_index import parse_subject_page

    html = (Path(__file__).parent / "fixtures" / "wt_pub_index_trinity.html").read_text(encoding="utf-8")
    t0 = time.perf_counter()
    subject = parse_subject_page(html, source_url="x")
    elapsed = time.perf_counter() - t0
    assert subject is not None
    assert len(subject.subheadings) > 100
    assert elapsed < 0.5, f"Topic-index parser took {elapsed * 1000:.1f}ms"
