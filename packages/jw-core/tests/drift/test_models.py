"""Drift Pydantic models."""

from __future__ import annotations

import pytest

from jw_core.drift.models import (
    Citation,
    DoctrinalDrift,
    DriftEvent,
    EraSnapshot,
    year_to_era,
)


def test_year_to_era_basic() -> None:
    assert year_to_era(1985) == "1980s"
    assert year_to_era(2024) == "2020s"
    assert year_to_era(1900) == "1900s"


def test_year_to_era_out_of_range() -> None:
    assert year_to_era(1899) is None
    assert year_to_era(2030) is None


def test_citation_round_trip() -> None:
    c = Citation(
        text="alma",
        wol_url="https://wol.jw.org/x",
        pub_code="w23.04",
        year=2023,
    )
    dumped = c.model_dump()
    rehydrated = Citation.model_validate(dumped)
    assert rehydrated.year == 2023


def test_era_snapshot_defaults() -> None:
    s = EraSnapshot(era="1980s", chunk_count=5)
    assert s.cluster_count == 0
    assert s.cluster_center_embedding_id == -1


def test_drift_event_rejects_invalid_significance() -> None:
    with pytest.raises(ValueError):
        DriftEvent(
            from_era="1980s",
            to_era="2020s",
            cosine_delta=0.2,
            significance="huge",  # type: ignore[arg-type]
            summary_change="x",
            from_citation=Citation(text="x", pub_code="x", year=1985),
            to_citation=Citation(text="x", pub_code="x", year=2024),
        )


def test_doctrinal_drift_minimal() -> None:
    d = DoctrinalDrift(
        query="alma",
        language="es",
        explanatory_note="Prov 4:18 ...",
    )
    assert d.drift_events == []
    assert d.insufficient_data is False
