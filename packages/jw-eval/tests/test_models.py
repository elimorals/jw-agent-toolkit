"""Tests for jw_eval.models."""

from __future__ import annotations

from datetime import datetime

import pytest

from jw_eval.models import GoldenCase, LayerResult, SuiteReport


def test_golden_case_minimal() -> None:
    case = GoldenCase(
        id="l1_demo",
        agent="apologetics",
        layer="l1",
        input={"question": "test"},
        expected={"min_findings": 1},
    )
    assert case.id == "l1_demo"
    assert case.layer == "l1"
    assert case.metadata == {}


def test_golden_case_rejects_invalid_layer() -> None:
    with pytest.raises(ValueError):
        GoldenCase(
            id="x",
            agent="apologetics",
            layer="l9",  # type: ignore[arg-type]
            input={},
            expected={},
        )


def test_layer_result_pass() -> None:
    r = LayerResult(
        case_id="l1_demo",
        layer="l1",
        verdict="pass",
        score=None,
        reasons=[],
        duration_ms=12,
    )
    assert r.verdict == "pass"
    assert r.score is None


def test_suite_report_summary_aggregates() -> None:
    now = datetime(2026, 5, 30, 12, 0, 0)
    results = [
        LayerResult(case_id="a", layer="l1", verdict="pass", score=None, reasons=[], duration_ms=1),
        LayerResult(case_id="b", layer="l1", verdict="fail", score=None, reasons=["x"], duration_ms=2),
        LayerResult(case_id="c", layer="l2", verdict="pass", score=None, reasons=[], duration_ms=3),
    ]
    report = SuiteReport(
        started_at=now,
        finished_at=now,
        layers_run=["l1", "l2"],
        results=results,
        summary=SuiteReport.summarize(results),
    )
    assert report.summary["l1"]["pass"] == 1
    assert report.summary["l1"]["fail"] == 1
    assert report.summary["l2"]["pass"] == 1
    assert report.summary["l2"]["fail"] == 0
