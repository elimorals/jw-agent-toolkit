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


from jw_core.citations.validator import _extract_urls, _parse_wol_url


def test_parse_wol_url_document_endpoint() -> None:
    url = "https://wol.jw.org/es/wol/d/r4/lp-s/1101989140"
    parsed = _parse_wol_url(url)
    assert parsed == {"doc_id": 1101989140, "pub_code": None, "iso": "es"}


def test_parse_wol_url_bible_chapter() -> None:
    url = "https://wol.jw.org/es/wol/b/r4/lp-s/nwt/E/2024/43/3"
    parsed = _parse_wol_url(url)
    assert parsed == {"doc_id": None, "pub_code": "nwt", "iso": "es"}


def test_parse_wol_url_unknown_pattern_returns_none() -> None:
    assert _parse_wol_url("https://b.jw-cdn.org/apis/foo") is None
    assert _parse_wol_url("https://example.com/random") is None


def test_extract_urls_from_dict_agent_output() -> None:
    out = {
        "findings": [
            {"text": "x", "metadata": {"citation_url": "https://wol.jw.org/x"}},
            {"text": "y", "metadata": {"citation_url": "https://wol.jw.org/y"}},
            {"text": "z", "metadata": {}},  # no URL
            {"text": "dup", "metadata": {"citation_url": "https://wol.jw.org/x"}},  # duplicate
        ]
    }
    urls = _extract_urls(out)
    assert urls == ["https://wol.jw.org/x", "https://wol.jw.org/y"]


def test_extract_urls_from_object_agent_output() -> None:
    class _Citation:
        url = "https://wol.jw.org/z"

    class _Finding:
        metadata: dict = {}
        citation = _Citation()

    class _Result:
        findings = [_Finding()]

    urls = _extract_urls(_Result())
    assert urls == ["https://wol.jw.org/z"]
