"""Tests for jw_core.concordance.models."""

from __future__ import annotations

import pytest
from jw_core.concordance.models import ConcordanceHit, IndexEntry


def test_index_entry_minimal() -> None:
    e = IndexEntry(
        source_kind="nwt",
        source_id="nwt:es:43:3",
        ref="Juan 3:16",
        chunk_text="Porque tanto amó Dios al mundo...",
        language="es",
    )
    assert e.source_kind == "nwt"
    assert e.url is None
    assert e.source_sha256 == ""


def test_index_entry_rejects_invalid_kind() -> None:
    with pytest.raises(ValueError):
        IndexEntry(
            source_kind="bogus",  # type: ignore[arg-type]
            source_id="x",
            ref="x",
            chunk_text="x",
            language="en",
        )


def test_concordance_hit_carries_snippet_with_markers() -> None:
    h = ConcordanceHit(
        entry_id=1,
        source_kind="epub",
        source_id="abc",
        ref="item-3:p5",
        snippet="...esto es ‹prueba› literal...",
        language="en",
        url=None,
    )
    assert "‹prueba›" in h.snippet
    assert h.url is None
