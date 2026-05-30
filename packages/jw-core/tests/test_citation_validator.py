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


from jw_core.citations import CitationValidator
from jw_core.integrations.meps_catalog import MepsCatalog


@pytest.mark.asyncio
async def test_structural_with_empty_catalog_returns_unknown(tmp_path) -> None:
    cat = MepsCatalog(db_path=tmp_path / "meps.db")
    v = CitationValidator(catalog=cat)
    report = await v.validate_urls(
        ["https://wol.jw.org/es/wol/d/r4/lp-s/1101989140"],
        mode="structural",
    )
    assert report.mode == "structural"
    assert len(report.checks) == 1
    check = report.checks[0]
    assert check.doc_id == 1101989140
    assert check.catalog == "missing"  # catalog empty - docId not found
    assert check.resolve == "skipped"
    assert check.is_ok is True


@pytest.mark.asyncio
async def test_structural_with_populated_catalog_ok(tmp_path) -> None:
    cat = MepsCatalog(db_path=tmp_path / "meps.db")
    # Hand-craft a publication+document row to avoid needing a real .jwpub.
    conn = cat._open()  # noqa: SLF001 — test-only access
    conn.execute(
        "INSERT INTO publication (pub_code, language_index, title) VALUES ('w24', 0, 'Watchtower')"
    )
    conn.execute(
        """INSERT INTO document
           (document_id, meps_document_id, pub_code, language_index, title)
           VALUES (1, 1101989140, 'w24', 0, 'Trinity?')"""
    )
    conn.commit()

    v = CitationValidator(catalog=cat)
    report = await v.validate_urls(
        ["https://wol.jw.org/es/wol/d/r4/lp-s/1101989140"],
        mode="structural",
    )
    check = report.checks[0]
    assert check.catalog == "ok"
    assert check.pub_code == "w24"


@pytest.mark.asyncio
async def test_structural_url_without_docid_is_unknown(tmp_path) -> None:
    cat = MepsCatalog(db_path=tmp_path / "meps.db")
    v = CitationValidator(catalog=cat)
    report = await v.validate_urls(
        ["https://wol.jw.org/es/wol/b/r4/lp-s/nwt/E/2024/43/3"],
        mode="structural",
    )
    check = report.checks[0]
    # Bible-chapter URLs carry pub_code but no doc_id — catalog can't disambiguate
    assert check.pub_code == "nwt"
    assert check.catalog == "unknown"


@pytest.mark.asyncio
async def test_validate_agent_output_dict(tmp_path) -> None:
    cat = MepsCatalog(db_path=tmp_path / "meps.db")
    v = CitationValidator(catalog=cat)
    agent_out = {
        "findings": [
            {"metadata": {"citation_url": "https://wol.jw.org/es/wol/d/r4/lp-s/1"}},
            {"metadata": {"citation_url": "https://wol.jw.org/es/wol/d/r4/lp-s/2"}},
        ]
    }
    report = await v.validate_agent_output(agent_out, mode="structural")
    assert len(report.checks) == 2
