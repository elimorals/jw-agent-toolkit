"""End-to-end drift engine tests (Fase 72)."""

from __future__ import annotations

import numpy as np

from jw_core.drift.cluster import Chunk
from jw_core.drift.engine import analyze_doctrinal_drift
from jw_core.drift.models import DoctrinalDrift


def _norm(v: list[float]) -> np.ndarray:
    arr = np.array(v, dtype=np.float32)
    n = float(np.linalg.norm(arr))
    return arr if n == 0 else (arr / n).astype(np.float32)


def _chunk(text: str, year: int, vec: list[float]) -> Chunk:
    return Chunk(text=text, year=year, embedding=_norm(vec))


def test_engine_insufficient_data_emits_note() -> None:
    out = analyze_doctrinal_drift(query="alma", chunks=[], language="es")
    assert isinstance(out, DoctrinalDrift)
    assert out.insufficient_data is True
    assert "Proverbios 4:18" in out.explanatory_note
    assert out.drift_events == []


def test_engine_explanatory_note_language_en() -> None:
    out = analyze_doctrinal_drift(query="x", chunks=[], language="en")
    assert "Proverbs 4:18" in out.explanatory_note


def test_engine_detects_drift_between_two_populated_eras() -> None:
    # 1980s cluster around [1, 0, 0], 2020s cluster around [0, 1, 0]
    chunks = [
        _chunk("a", 1985, [1.0, 0.0, 0.0]),
        _chunk("b", 1986, [0.99, 0.05, 0.0]),
        _chunk("c", 1987, [1.0, 0.05, 0.0]),
        _chunk("d", 2024, [0.0, 1.0, 0.0]),
        _chunk("e", 2025, [0.05, 0.99, 0.0]),
        _chunk("f", 2026, [0.0, 1.0, 0.05]),
    ]
    out = analyze_doctrinal_drift(
        query="alma",
        chunks=chunks,
        language="es",
        min_chunks_per_era=3,
    )
    assert out.insufficient_data is False
    assert len(out.era_snapshots) == 2
    assert out.drift_events
    e = out.drift_events[0]
    assert e.from_era == "1980s"
    assert e.to_era == "2020s"
    assert e.significance in ("minor", "moderate", "major")
    # Summary prose mentions the drift line
    assert "1980s" in out.summary_prose
    assert "2020s" in out.summary_prose


def test_engine_skips_eras_with_few_chunks() -> None:
    chunks = [
        _chunk("a", 1985, [1.0, 0.0]),
        _chunk("b", 1986, [0.99, 0.0]),
        _chunk("c", 1987, [1.0, 0.05]),
        _chunk("d", 2024, [0.0, 1.0]),  # only 1 chunk -> skipped
    ]
    out = analyze_doctrinal_drift(
        query="x",
        chunks=chunks,
        language="es",
        min_chunks_per_era=3,
    )
    assert "2020s" in out.eras_skipped_low_data
    # Only one populated era -> insufficient
    assert out.insufficient_data is True


def test_engine_no_drift_when_centers_stable() -> None:
    # Same cluster shape across eras
    chunks = [
        _chunk("a", 1985, [1.0, 0.0]),
        _chunk("b", 1986, [0.99, 0.01]),
        _chunk("c", 1987, [1.0, 0.0]),
        _chunk("d", 2024, [1.0, 0.0]),
        _chunk("e", 2025, [0.99, 0.01]),
        _chunk("f", 2026, [1.0, 0.0]),
    ]
    out = analyze_doctrinal_drift(
        query="x",
        chunks=chunks,
        language="es",
        min_chunks_per_era=3,
        min_delta=0.05,
    )
    assert out.insufficient_data is False
    assert out.drift_events == []
    assert "Sin" in out.summary_prose or "No" in out.summary_prose
