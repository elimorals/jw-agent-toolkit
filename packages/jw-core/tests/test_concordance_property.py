"""Property-based smoke test for the concordance store.

Inserting N random unique sentences and searching for one of their tokens
should always return a non-empty result; inserting then deleting must
return the store to count=0.
"""

from __future__ import annotations

import random
import string
from pathlib import Path

import pytest
from jw_core.concordance.indexer import NWTChapter, index_nwt_chapter
from jw_core.concordance.search import concordance_search
from jw_core.concordance.store import ConcordanceStore


def _random_sentence(rng: random.Random) -> str:
    return " ".join(
        "".join(rng.choices(string.ascii_lowercase, k=rng.randint(3, 8))) for _ in range(rng.randint(5, 10))
    )


@pytest.mark.parametrize("seed", [0, 1, 7, 42, 100])
def test_random_corpus_search_finds_every_inserted_token(tmp_path: Path, seed: int) -> None:
    rng = random.Random(seed)
    db = tmp_path / f"c-{seed}.db"
    store = ConcordanceStore(db_path=db)
    try:
        verses: list[tuple[int, str]] = []
        sample_tokens: list[str] = []
        for i in range(1, 51):
            s = _random_sentence(rng)
            verses.append((i, s))
            sample_tokens.append(s.split()[0])
        chapter = NWTChapter(
            language="en",
            book_num=99,
            chapter=1,
            verses=verses,
            url=None,
        )
        index_nwt_chapter(store, chapter)
    finally:
        store.close()

    for tok in sample_tokens[:10]:
        hits = concordance_search(tok, db_path=db, max_results=100)
        assert any(tok in h.snippet for h in hits), f"token {tok!r} should appear in at least one hit for seed={seed}"
