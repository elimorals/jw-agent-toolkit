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


# ── Task 5: live mode + redirects + concurrency ────────────────────────

import asyncio

from jw_core.citations.validator import FetcherResponse


def _fake_fetcher_factory(table: dict[str, FetcherResponse]):
    async def fetch(url: str) -> FetcherResponse:
        if url not in table:
            raise RuntimeError(f"unexpected URL {url}")
        return table[url]

    return fetch


@pytest.mark.asyncio
async def test_live_ok(tmp_path) -> None:
    cat = MepsCatalog(db_path=tmp_path / "meps.db")
    url = "https://wol.jw.org/es/wol/d/r4/lp-s/1"
    fetcher = _fake_fetcher_factory(
        {url: FetcherResponse(final_url=url, status=200, redirect_chain=[], body="<p>ok</p>")}
    )
    v = CitationValidator(catalog=cat, fetcher=fetcher)
    report = await v.validate_urls([url], mode="live")
    assert report.checks[0].resolve == "ok"
    assert report.checks[0].http_status == 200


@pytest.mark.asyncio
async def test_live_ok_redirect(tmp_path) -> None:
    cat = MepsCatalog(db_path=tmp_path / "meps.db")
    url = "https://wol.jw.org/es/wol/d/r4/lp-s/1"
    fetcher = _fake_fetcher_factory(
        {
            url: FetcherResponse(
                final_url="https://wol.jw.org/es/wol/d/r4/lp-s/2",
                status=200,
                redirect_chain=["https://wol.jw.org/es/wol/d/r4/lp-s/1"],
                body="<p>ok</p>",
            )
        }
    )
    v = CitationValidator(catalog=cat, fetcher=fetcher)
    report = await v.validate_urls([url], mode="live")
    check = report.checks[0]
    assert check.resolve == "ok_redirect"
    assert check.redirect_chain == ["https://wol.jw.org/es/wol/d/r4/lp-s/1"]
    assert check.is_ok is True
    assert report.summary["warning"] >= 1


@pytest.mark.asyncio
async def test_live_404(tmp_path) -> None:
    cat = MepsCatalog(db_path=tmp_path / "meps.db")
    url = "https://wol.jw.org/es/wol/d/r4/lp-s/9999999"
    fetcher = _fake_fetcher_factory({url: FetcherResponse(final_url=url, status=404)})
    v = CitationValidator(catalog=cat, fetcher=fetcher)
    report = await v.validate_urls([url], mode="live")
    assert report.checks[0].resolve == "not_found"
    assert report.checks[0].is_ok is False
    assert report.summary["failed"] == 1


@pytest.mark.asyncio
async def test_live_redirect_loop(tmp_path) -> None:
    cat = MepsCatalog(db_path=tmp_path / "meps.db")
    url = "https://wol.jw.org/es/wol/d/r4/lp-s/1"
    chain = [f"https://wol.jw.org/r/{i}" for i in range(5)]  # 5 > max_redirects 3
    fetcher = _fake_fetcher_factory(
        {url: FetcherResponse(final_url=url, status=200, redirect_chain=chain)}
    )
    v = CitationValidator(catalog=cat, fetcher=fetcher, max_redirects=3)
    report = await v.validate_urls([url], mode="live")
    assert report.checks[0].resolve == "redirect_loop"


@pytest.mark.asyncio
async def test_live_network_error_is_isolated(tmp_path) -> None:
    cat = MepsCatalog(db_path=tmp_path / "meps.db")

    async def fetcher(url: str) -> FetcherResponse:
        raise TimeoutError("connection timed out")

    v = CitationValidator(catalog=cat, fetcher=fetcher)
    report = await v.validate_urls(["https://wol.jw.org/es/wol/d/r4/lp-s/1"], mode="live")
    assert report.checks[0].resolve == "network_error"
    assert report.checks[0].is_ok is False


@pytest.mark.asyncio
async def test_concurrency_is_bounded(tmp_path) -> None:
    cat = MepsCatalog(db_path=tmp_path / "meps.db")

    live: int = 0
    peak: int = 0
    lock = asyncio.Lock()

    async def slow_fetcher(url: str) -> FetcherResponse:
        nonlocal live, peak
        async with lock:
            live += 1
            peak = max(peak, live)
        await asyncio.sleep(0.05)
        async with lock:
            live -= 1
        return FetcherResponse(final_url=url, status=200)

    v = CitationValidator(catalog=cat, fetcher=slow_fetcher, concurrency=3)
    urls = [f"https://wol.jw.org/es/wol/d/r4/lp-s/{i}" for i in range(10)]
    await v.validate_urls(urls, mode="live")
    assert peak <= 3, f"peak concurrency {peak} > limit 3"


@pytest.mark.asyncio
async def test_live_requires_fetcher(tmp_path) -> None:
    cat = MepsCatalog(db_path=tmp_path / "meps.db")
    v = CitationValidator(catalog=cat)
    with pytest.raises(ValueError):
        await v.validate_urls(["https://wol.jw.org/x"], mode="live")


# ── Task 6: drift mode ─────────────────────────────────────────────────

import hashlib


@pytest.mark.asyncio
async def test_drift_no_snapshot_is_warning(tmp_path) -> None:
    cat = MepsCatalog(db_path=tmp_path / "meps.db")
    snaps = tmp_path / "snaps"
    snaps.mkdir()
    url = "https://wol.jw.org/es/wol/d/r4/lp-s/1"
    fetcher = _fake_fetcher_factory(
        {url: FetcherResponse(final_url=url, status=200, body="<html>hi</html>")}
    )
    v = CitationValidator(catalog=cat, fetcher=fetcher, snapshots_root=snaps)
    report = await v.validate_urls([url], mode="live+drift")
    check = report.checks[0]
    assert check.drift == "no_snapshot"
    assert check.is_ok is True  # is_ok lenient — but summary counts as warning
    assert report.summary["warning"] >= 1


@pytest.mark.asyncio
async def test_drift_ok_when_snapshot_present_and_resolves(tmp_path) -> None:
    cat = MepsCatalog(db_path=tmp_path / "meps.db")
    snaps = tmp_path / "snaps"
    snaps.mkdir()
    url = "https://wol.jw.org/es/wol/d/r4/lp-s/1"
    digest = hashlib.sha256(url.encode()).hexdigest()
    (snaps / f"{digest}.html").write_text("<html>known content</html>", encoding="utf-8")
    fetcher = _fake_fetcher_factory(
        {url: FetcherResponse(final_url=url, status=200, body="<html>known content</html>")}
    )
    v = CitationValidator(catalog=cat, fetcher=fetcher, snapshots_root=snaps)
    report = await v.validate_urls([url], mode="live+drift")
    assert report.checks[0].drift == "ok"


@pytest.mark.asyncio
async def test_drift_detected_when_shape_changes(tmp_path) -> None:
    cat = MepsCatalog(db_path=tmp_path / "meps.db")
    snaps = tmp_path / "snaps"
    snaps.mkdir()
    url = "https://wol.jw.org/es/wol/d/r4/lp-s/1"
    digest = hashlib.sha256(url.encode()).hexdigest()
    (snaps / f"{digest}.html").write_text(
        "<html><body><p>old</p></body></html>", encoding="utf-8"
    )
    # Live body is structurally different (extra div changes the shape).
    fetcher = _fake_fetcher_factory(
        {
            url: FetcherResponse(
                final_url=url,
                status=200,
                body="<html><body><div><p>new</p><span>x</span></div></body></html>",
            )
        }
    )
    v = CitationValidator(catalog=cat, fetcher=fetcher, snapshots_root=snaps)
    report = await v.validate_urls([url], mode="live+drift")
    assert report.checks[0].drift == "drift"


@pytest.mark.asyncio
async def test_live_drift_requires_snapshots_root(tmp_path) -> None:
    cat = MepsCatalog(db_path=tmp_path / "meps.db")
    fetcher = _fake_fetcher_factory({})
    v = CitationValidator(catalog=cat, fetcher=fetcher)
    with pytest.raises(ValueError):
        await v.validate_urls(["x"], mode="live+drift")


# ── Task 7: httpx_fetcher adapter ──────────────────────────────────────

import httpx


@pytest.mark.asyncio
async def test_httpx_fetcher_follows_redirect_chain() -> None:
    from jw_core.citations.validator import httpx_fetcher

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/a":
            return httpx.Response(301, headers={"Location": "/b"})
        if request.url.path == "/b":
            return httpx.Response(200, text="final")
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport, base_url="https://wol.jw.org") as client:
        fetcher = httpx_fetcher(client)
        resp = await fetcher("https://wol.jw.org/a")
    assert resp.status == 200
    assert resp.final_url.endswith("/b")
    assert resp.redirect_chain  # non-empty
    assert "final" in resp.body
