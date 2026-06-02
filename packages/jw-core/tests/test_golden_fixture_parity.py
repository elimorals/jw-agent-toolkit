"""Verify the shared parser golden fixture against the Python implementation.

The same JSON (`shared/data/bible_references_golden.json`) is consumed by
the TypeScript port at `packages/jw-core-js/tests/parser.test.ts`. Both
implementations must agree on every row; if either side drifts, this test
or its TS counterpart fails.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from jw_core.parsers.reference import parse_reference

FIXTURE = (
    Path(__file__).parent.parent.parent.parent
    / "shared"
    / "data"
    / "bible_references_golden.json"
)


def _cases() -> list[dict]:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))["cases"]


@pytest.mark.parametrize("case", _cases(), ids=lambda c: c["input"])
def test_python_parser_matches_shared_fixture(case: dict) -> None:
    ref = parse_reference(case["input"])
    assert ref is not None, f"expected a match for {case['input']!r}"
    assert ref.book_num == case["book_num"]
    assert ref.book_canonical == case["book_canonical"]
    assert ref.chapter == case["chapter"]
    expected_start = case["verse_start"]
    expected_end = case["verse_end"]
    assert (ref.verse_start or None) == expected_start
    assert (ref.verse_end or None) == expected_end
