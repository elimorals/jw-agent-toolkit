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
    """Every field in the fixture must round-trip through `parse_reference`.

    F56.3: also verifies `detected_language` and `raw_match`. Prior versions
    only checked book/chapter/verses, so any drift in language detection
    or token-matching went silent. Older fixtures (v1.0, 17 cases) lacked
    those fields entirely — we honor them when present.
    """
    ref = parse_reference(case["input"])
    assert ref is not None, f"expected a match for {case['input']!r}"
    assert ref.book_num == case["book_num"]
    assert ref.book_canonical == case["book_canonical"]
    assert ref.chapter == case["chapter"]
    assert (ref.verse_start or None) == case["verse_start"]
    assert (ref.verse_end or None) == case["verse_end"]
    if "detected_language" in case:
        assert ref.detected_language == case["detected_language"], (
            f"language drift on {case['input']!r}: parser={ref.detected_language!r} "
            f"fixture={case['detected_language']!r}"
        )
    if "raw_match" in case:
        assert ref.raw_match == case["raw_match"]
