"""SVG drift visualization tests (Fase 72 post-MVP)."""

from __future__ import annotations

from jw_core.drift.models import (
    Citation,
    DoctrinalDrift,
    DriftEvent,
    EraSnapshot,
)
from jw_core.drift.svg import drift_to_svg


def _report(**kw) -> DoctrinalDrift:
    return DoctrinalDrift(
        query="alma",
        language="es",
        era_snapshots=kw.get(
            "era_snapshots",
            [
                EraSnapshot(era="1980s", chunk_count=3),
                EraSnapshot(era="2020s", chunk_count=3),
            ],
        ),
        drift_events=kw.get(
            "drift_events",
            [
                DriftEvent(
                    from_era="1980s",
                    to_era="2020s",
                    cosine_delta=0.42,
                    significance="major",
                    summary_change="shift",
                    from_citation=Citation(
                        text="old", pub_code="", year=1985
                    ),
                    to_citation=Citation(
                        text="new", pub_code="", year=2024
                    ),
                )
            ],
        ),
        explanatory_note="Prov 4:18 nota.",
    )


def test_svg_starts_with_svg_and_ends() -> None:
    out = drift_to_svg(_report())
    assert out.startswith("<svg")
    assert out.endswith("</svg>")


def test_svg_renders_all_13_eras_as_squares() -> None:
    out = drift_to_svg(_report())
    # 13 era markers labels
    for era in (
        "1900s",
        "1950s",
        "2020s",
    ):
        assert f">{era}</text>" in out


def test_svg_renders_drift_arrow_with_significance_label() -> None:
    out = drift_to_svg(_report())
    assert "major" in out
    assert "Δ=0.42" in out


def test_svg_xml_escapes_query() -> None:
    rep = _report()
    rep.query = 'alma "test" <bad>'
    out = drift_to_svg(rep)
    assert "&quot;" in out
    assert "&lt;bad&gt;" in out


def test_svg_handles_empty_drift_events() -> None:
    rep = _report(drift_events=[])
    out = drift_to_svg(rep)
    assert "<svg" in out


def test_svg_includes_explanatory_note_truncated() -> None:
    rep = _report()
    rep.explanatory_note = "Prov 4:18 " + ("x" * 500)
    out = drift_to_svg(rep)
    # Note must be truncated
    assert out.count("xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx") <= 6
