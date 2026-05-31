"""Tests for simhash-based near-duplicate detection."""

from __future__ import annotations

from jw_finetune.data.dedupe import deduplicate, hamming_distance, simhash
from jw_finetune.data.models import ParagraphRecord


def _rec(text: str) -> ParagraphRecord:
    return ParagraphRecord(
        text=text,
        pub_code="w24",
        language="es",
        kind="watchtower",
        source_path="x",
    )


def test_simhash_stable() -> None:
    h1 = simhash("Hello world this is a test")
    h2 = simhash("Hello world this is a test")
    assert h1 == h2


def test_simhash_similar_close() -> None:
    h1 = simhash("Hello world this is a test sentence")
    h2 = simhash("Hello world this is a test sentence!")
    assert hamming_distance(h1, h2) < 5


def test_simhash_different_far() -> None:
    h1 = simhash("The cat sat on the mat lazily today")
    h2 = simhash("Quantum chromodynamics describes the strong nuclear force")
    assert hamming_distance(h1, h2) > 15


def test_simhash_empty_returns_zero() -> None:
    assert simhash("") == 0
    assert simhash("   ") == 0


def test_hamming_zero_for_equal() -> None:
    assert hamming_distance(0xDEADBEEF, 0xDEADBEEF) == 0


def test_deduplicate_removes_near_duplicates() -> None:
    records = [
        _rec("In the beginning God created the heavens and the earth."),
        _rec("In the beginning God created the heavens and the earth!"),
        _rec("The earth was formless and waste."),
    ]
    deduped = list(deduplicate(records, threshold=4))
    assert len(deduped) == 2


def test_deduplicate_preserves_order() -> None:
    """First occurrence is kept."""
    records = [_rec(f"unique sentence number {i} with words") for i in range(5)]
    deduped = list(deduplicate(records, threshold=4))
    assert len(deduped) == 5
    assert deduped[0].text == records[0].text
