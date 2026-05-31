"""Near-duplicate detection via Charikar simhash (64-bit).

Why simhash and not embedding-based dedup? Two reasons:
  1. No dependency on a GPU or embedding service; runs on CPU in pure Python.
  2. Hamming distance on a 64-bit fingerprint is constant-time per comparison.

For tens of thousands of paragraphs this is more than fast enough. If the
corpus grows much larger, swap in `jw_rag.embed.Embedder` + cosine and
make this a strategy.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Iterable, Iterator

from jw_finetune.data.models import ParagraphRecord

_TOKEN_RE = re.compile(r"\w+", re.UNICODE)


def _tokens(text: str) -> list[str]:
    return [t.lower() for t in _TOKEN_RE.findall(text)]


def _hash64(token: str) -> int:
    return int.from_bytes(
        hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest(),
        "big",
    )


def simhash(text: str, *, bits: int = 64) -> int:
    """Charikar simhash. Returns a `bits`-wide int (default 64)."""
    tokens = _tokens(text)
    if not tokens:
        return 0
    vec = [0] * bits
    for tok in tokens:
        h = _hash64(tok)
        for i in range(bits):
            if h & (1 << (bits - 1 - i)):
                vec[i] += 1
            else:
                vec[i] -= 1
    out = 0
    for i in range(bits):
        if vec[i] > 0:
            out |= 1 << (bits - 1 - i)
    return out


def hamming_distance(a: int, b: int) -> int:
    """Population count of XOR. Python 3.10+ has `int.bit_count()`."""
    return (a ^ b).bit_count()


def deduplicate(
    records: Iterable[ParagraphRecord],
    *,
    threshold: int = 4,
) -> Iterator[ParagraphRecord]:
    """Yield records skipping any whose simhash is within `threshold` of a prior.

    First occurrence wins. O(N·M) where M = unique fingerprints kept so far.
    """
    seen: list[int] = []
    for r in records:
        h = simhash(r.text)
        if any(hamming_distance(h, s) <= threshold for s in seen):
            continue
        seen.append(h)
        yield r
