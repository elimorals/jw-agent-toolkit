"""L2 — Citation integrity eval.

Two modes:
  - SNAPSHOT mode: HTML snapshots commited to repo. Offline, deterministic.
                   Used by default in CI.
  - LIVE mode: re-fetches the URL with WOLClient and compares.
               Cron weekly, opens issues on drift. (Live mode added in Task 8.)

A case passes if:
  1) Agent output contains every URL listed in `expected_citations`.
  2) For each URL, the snapshot contains at least one phrase from
     `support_phrases`.

Snapshot location: `<snapshots_root>/<sha256(URL)>.html`.
"""

from __future__ import annotations

import hashlib
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from jw_eval.models import GoldenCase, LayerResult


def snapshot_path(root: Path, url: str) -> Path:
    digest = hashlib.sha256(url.encode("utf-8")).hexdigest()
    return root / f"{digest}.html"


def _extract_urls(result: Any) -> list[str]:
    """Pull URLs out of an AgentResult-like object's findings."""

    urls: list[str] = []
    for f in getattr(result, "findings", []) or []:
        meta = getattr(f, "metadata", {}) or {}
        # Convention: citation URL lives at metadata.citation_url OR finding.citation.url
        url = meta.get("citation_url")
        if not url:
            citation = getattr(f, "citation", None)
            url = getattr(citation, "url", None) if citation else None
        if url:
            urls.append(url)
    return urls


def evaluate_citations_snapshot(
    case: GoldenCase,
    agent: Callable[[dict[str, Any]], Any],
    snapshots_root: Path,
) -> LayerResult:
    """Evaluate an L2 case in snapshot (offline) mode."""

    started = time.monotonic()
    expected_urls = case.expected.get("expected_citations") or []
    phrases = case.expected.get("support_phrases") or []
    reasons: list[str] = []

    try:
        result = agent(case.input)
    except Exception as exc:
        return LayerResult(
            case_id=case.id,
            layer="l2",
            verdict="error",
            reasons=[f"agent raised: {exc!r}"],
            duration_ms=int((time.monotonic() - started) * 1000),
        )

    actual_urls = _extract_urls(result)
    for url in expected_urls:
        if url not in actual_urls:
            reasons.append(f"missing URL {url} (got {actual_urls})")

    # If we already have URL-level failures, that's a hard fail — report it
    # regardless of whether snapshots are present.
    if reasons:
        return LayerResult(
            case_id=case.id,
            layer="l2",
            verdict="fail",
            reasons=reasons,
            duration_ms=int((time.monotonic() - started) * 1000),
        )

    # If we don't have snapshots for the URLs, skip — do not fail.
    missing_snaps = [u for u in expected_urls if not snapshot_path(snapshots_root, u).exists()]
    if missing_snaps:
        return LayerResult(
            case_id=case.id,
            layer="l2",
            verdict="skip",
            reasons=[f"no snapshot for {u}" for u in missing_snaps],
            duration_ms=int((time.monotonic() - started) * 1000),
        )

    for url in expected_urls:
        html = snapshot_path(snapshots_root, url).read_text(encoding="utf-8")
        if not any(p.lower() in html.lower() for p in phrases):
            reasons.append(f"none of support_phrases {phrases} found in snapshot of {url}")

    verdict = "pass" if not reasons else "fail"
    return LayerResult(
        case_id=case.id,
        layer="l2",
        verdict=verdict,
        reasons=reasons,
        duration_ms=int((time.monotonic() - started) * 1000),
    )


def evaluate_citations_live(
    case: GoldenCase,
    agent: Callable[[dict[str, Any]], Any],
    fetcher: Callable[[str], str],
) -> LayerResult:
    """Evaluate an L2 case live: re-fetch URLs via `fetcher` callback."""

    started = time.monotonic()
    expected_urls = case.expected.get("expected_citations") or []
    phrases = case.expected.get("support_phrases") or []
    reasons: list[str] = []

    try:
        result = agent(case.input)
    except Exception as exc:
        return LayerResult(
            case_id=case.id,
            layer="l2",
            verdict="error",
            reasons=[f"agent raised: {exc!r}"],
            duration_ms=int((time.monotonic() - started) * 1000),
        )

    actual_urls = _extract_urls(result)
    for url in expected_urls:
        if url not in actual_urls:
            reasons.append(f"missing URL {url} (got {actual_urls})")

    for url in expected_urls:
        try:
            html = fetcher(url)
        except Exception as exc:  # noqa: BLE001
            reasons.append(f"fetch failed for {url}: {exc!r}")
            continue
        if not any(p.lower() in html.lower() for p in phrases):
            reasons.append(f"live: none of {phrases} found in {url}")

    verdict = "pass" if not reasons else "fail"
    return LayerResult(
        case_id=case.id,
        layer="l2",
        verdict=verdict,
        reasons=reasons,
        duration_ms=int((time.monotonic() - started) * 1000),
    )
