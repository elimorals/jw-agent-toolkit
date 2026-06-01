"""Tests for ProvenanceValidator — fetcher is injected, never real network."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import pytest

from jw_agents.base import Citation, Finding
from jw_core.provenance.hashing import content_sha256
from jw_core.provenance.validator import (
    FetcherResponse,
    ProvenanceValidator,
)


@dataclass
class FakeFetcher:
    """Maps URL → (status, body). Async-callable like the production fetcher."""

    canned: dict[str, tuple[int, str]] = field(default_factory=dict)
    calls: list[str] = field(default_factory=list)
    raise_for: set[str] = field(default_factory=set)

    async def __call__(self, url: str) -> FetcherResponse:
        self.calls.append(url)
        if url in self.raise_for:
            raise RuntimeError(f"forced failure for {url}")
        status, body = self.canned.get(url, (404, ""))
        return FetcherResponse(final_url=url, status=status, body=body)


def _stamped_citation(text: str, *, url: str = "https://wol.jw.org/x") -> Citation:
    """Build a citation as if the parser had stamped it with provenance."""

    return Citation(
        url=url,
        title="t",
        kind="verse",
        metadata={
            "accessed_at": "2026-05-30T10:00:00Z",
            "content_hash": content_sha256(text),
            "published_date": "2024-01-01",
            "revision": "rev. 2023",
        },
    )


async def test_check_match_when_content_unchanged() -> None:
    text = "Jehová amó tanto al mundo"
    cit = _stamped_citation(text)
    fetcher = FakeFetcher(canned={cit.url: (200, text)})

    validator = ProvenanceValidator(fetcher=fetcher)
    verdict = await validator.check(cit)

    assert verdict.status == "match"
    assert verdict.original_hash == verdict.current_hash
    assert verdict.delta_chars == 0
    assert fetcher.calls == [cit.url]


async def test_check_changed_when_text_edited() -> None:
    original_text = "Jehová amó tanto al mundo"
    new_text = "Jehová amó tanto al universo"
    cit = _stamped_citation(original_text)
    fetcher = FakeFetcher(canned={cit.url: (200, new_text)})

    validator = ProvenanceValidator(fetcher=fetcher)
    verdict = await validator.check(cit)

    assert verdict.status == "changed"
    assert verdict.original_hash != verdict.current_hash
    assert verdict.delta_chars is not None
    assert verdict.delta_chars >= 0


async def test_check_unreachable_when_fetcher_raises() -> None:
    cit = _stamped_citation("doesn't matter")
    fetcher = FakeFetcher(raise_for={cit.url})

    validator = ProvenanceValidator(fetcher=fetcher)
    verdict = await validator.check(cit)

    assert verdict.status == "unreachable"
    assert verdict.current_hash is None
    assert any("forced failure" in n for n in verdict.notes)


async def test_check_unreachable_when_non_2xx() -> None:
    cit = _stamped_citation("text")
    fetcher = FakeFetcher(canned={cit.url: (404, "")})

    validator = ProvenanceValidator(fetcher=fetcher)
    verdict = await validator.check(cit)

    assert verdict.status == "unreachable"
    assert any("404" in n for n in verdict.notes)


async def test_check_no_record_when_citation_lacks_provenance() -> None:
    """Backwards compat: legacy citations have no content_hash → no_record."""

    cit = Citation(url="https://wol.jw.org/x", title="t", kind="verse", metadata={})
    fetcher = FakeFetcher(canned={cit.url: (200, "anything")})

    validator = ProvenanceValidator(fetcher=fetcher)
    verdict = await validator.check(cit)

    assert verdict.status == "no_record"
    assert verdict.original_hash is None
    assert fetcher.calls == []


async def test_check_uses_injected_extractor() -> None:
    """If the fetcher returns HTML, the extractor turns it into plain text first."""

    canonical_text = "Jehová amó tanto al mundo"
    html = f"<html><body><p>{canonical_text}</p></body></html>"
    cit = _stamped_citation(canonical_text)

    def text_only(body: str) -> str:
        import re

        return re.sub(r"<[^>]+>", " ", body)

    fetcher = FakeFetcher(canned={cit.url: (200, html)})
    validator = ProvenanceValidator(fetcher=fetcher, extractor=text_only)
    verdict = await validator.check(cit)

    assert verdict.status == "match"


async def test_check_agent_output_paralellizes_unique_urls() -> None:
    """Two findings, same URL → fetcher called once."""

    text = "shared body"
    cit_a = _stamped_citation(text, url="https://wol.jw.org/shared")
    cit_b = _stamped_citation(text, url="https://wol.jw.org/shared")
    finding_a = Finding(summary="a", citation=cit_a, excerpt=text)
    finding_b = Finding(summary="b", citation=cit_b, excerpt=text)

    class _R:
        findings = [finding_a, finding_b]

    fetcher = FakeFetcher(canned={cit_a.url: (200, text)})
    validator = ProvenanceValidator(fetcher=fetcher)
    report = await validator.check_agent_output(_R())

    assert len(report.verdicts) == 2
    assert all(v.status == "match" for v in report.verdicts)
    assert fetcher.calls.count(cit_a.url) == 1
    assert report.summary["match"] == 2


async def test_check_since_filters_by_accessed_at_threshold() -> None:
    """Only re-check citations accessed BEFORE the `since` cutoff."""

    text = "body"
    old = _stamped_citation(text, url="https://wol.jw.org/old")
    old.metadata["accessed_at"] = "2026-01-01T00:00:00Z"
    new = _stamped_citation(text, url="https://wol.jw.org/new")
    new.metadata["accessed_at"] = "2026-05-31T00:00:00Z"

    class _F:
        def __init__(self, c: Citation) -> None:
            self.citation = c
            self.metadata: dict[str, Any] = {}

    class _R:
        findings = [_F(old), _F(new)]

    fetcher = FakeFetcher(canned={old.url: (200, text), new.url: (200, text)})
    validator = ProvenanceValidator(fetcher=fetcher)
    report = await validator.check_since(
        _R(),
        since=datetime(2026, 3, 1, tzinfo=timezone.utc),
    )

    skipped = [v for v in report.verdicts if v.status == "skipped"]
    matched = [v for v in report.verdicts if v.status == "match"]
    assert len(skipped) == 1
    assert skipped[0].url == new.url
    assert len(matched) == 1
    assert matched[0].url == old.url
    assert fetcher.calls == [old.url]


async def test_check_agent_output_aggregates_summary() -> None:
    """Mixed outcomes — summary counts each status."""

    text_match = "x"
    text_orig = "y"
    text_drift = "z"

    cit_match = _stamped_citation(text_match, url="https://wol.jw.org/a")
    cit_drift = _stamped_citation(text_orig, url="https://wol.jw.org/b")
    cit_dead = _stamped_citation(text_match, url="https://wol.jw.org/c")
    cit_legacy = Citation(url="https://wol.jw.org/d", metadata={})

    class _F:
        def __init__(self, c: Citation) -> None:
            self.citation = c
            self.metadata: dict[str, Any] = {}

    class _R:
        findings = [_F(cit_match), _F(cit_drift), _F(cit_dead), _F(cit_legacy)]

    fetcher = FakeFetcher(
        canned={
            cit_match.url: (200, text_match),
            cit_drift.url: (200, text_drift),
            cit_dead.url: (500, ""),
            cit_legacy.url: (200, "irrelevant"),
        }
    )
    validator = ProvenanceValidator(fetcher=fetcher)
    report = await validator.check_agent_output(_R())

    assert report.summary["match"] == 1
    assert report.summary["changed"] == 1
    assert report.summary["unreachable"] == 1
    assert report.summary["no_record"] == 1
