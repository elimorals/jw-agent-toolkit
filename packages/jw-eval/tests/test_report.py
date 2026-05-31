from __future__ import annotations

from datetime import datetime

from jw_eval.models import LayerResult, SuiteReport
from jw_eval.report import to_json, to_markdown


def _sample() -> SuiteReport:
    now = datetime(2026, 5, 30, 12, 0, 0)
    results = [
        LayerResult(case_id="a", layer="l1", verdict="pass", reasons=[], duration_ms=5),
        LayerResult(case_id="b", layer="l1", verdict="fail", reasons=["missing source"], duration_ms=6),
        LayerResult(case_id="c", layer="l3", verdict="pass", score=0.91, reasons=[], duration_ms=200),
    ]
    return SuiteReport(
        started_at=now,
        finished_at=now,
        layers_run=["l1", "l3"],
        results=results,
        summary=SuiteReport.summarize(results),
    )


def test_markdown_has_table_and_failures() -> None:
    md = to_markdown(_sample())
    assert "# jw-eval report" in md
    assert "| l1 |" in md
    assert "missing source" in md
    assert "0.91" in md


def test_json_roundtrips() -> None:
    rep = _sample()
    js = to_json(rep)
    assert '"verdict": "pass"' in js
    assert '"case_id": "b"' in js
