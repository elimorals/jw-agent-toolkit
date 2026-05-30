"""Tests for jw_core.citations."""

from __future__ import annotations

import pytest

from jw_core.citations.models import (
    CatalogStatus,
    CitationCheck,
    CitationReport,
    DriftStatus,
    ResolveStatus,
)


def test_citation_check_defaults_are_skipped() -> None:
    c = CitationCheck(url="https://wol.jw.org/x")
    assert c.resolve == "skipped"
    assert c.catalog == "unknown"
    assert c.drift == "skipped"
    assert c.is_ok is True


def test_citation_check_fails_on_404() -> None:
    c = CitationCheck(url="https://wol.jw.org/x", resolve="not_found", http_status=404)
    assert c.is_ok is False


def test_citation_check_warns_on_redirect() -> None:
    c = CitationCheck(
        url="https://wol.jw.org/x",
        resolve="ok_redirect",
        http_status=200,
        redirect_chain=["https://wol.jw.org/y"],
    )
    # is_ok stays True, but the summarizer should count it as warning.
    assert c.is_ok is True


def test_citation_report_summarize_counts() -> None:
    checks = [
        CitationCheck(url="a", resolve="ok", http_status=200),
        CitationCheck(url="b", resolve="ok_redirect", http_status=200, redirect_chain=["c"]),
        CitationCheck(url="c", resolve="not_found", http_status=404),
        CitationCheck(url="d", resolve="ok", http_status=200, drift="no_snapshot"),
    ]
    report = CitationReport(
        mode="live",
        checks=checks,
        summary=CitationReport.summarize(checks),
    )
    assert report.summary["total"] == 4
    assert report.summary["ok"] == 1
    assert report.summary["warning"] == 2  # redirect + no_snapshot
    assert report.summary["failed"] == 1
