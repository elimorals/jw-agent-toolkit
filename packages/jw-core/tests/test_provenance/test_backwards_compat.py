"""Backwards compat: legacy AgentResults (pre-Fase 40) must still process cleanly.

The validator MUST NOT crash on citations lacking provenance keys.
Every such citation gets verdict `no_record` and the fetcher is NOT
called for them (no wasted network).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jw_agents.base import Citation, Finding
from jw_core.provenance.validator import FetcherResponse, ProvenanceValidator

FIXTURE = Path(__file__).parent / "fixtures" / "agent_result_legacy.json"


class _CountingFetcher:
    def __init__(self) -> None:
        self.calls: list[str] = []

    async def __call__(self, url: str) -> FetcherResponse:
        self.calls.append(url)
        return FetcherResponse(final_url=url, status=200, body="should not be hashed")


def _hydrate(raw: dict[str, Any]):
    findings: list[Finding] = []
    for f in raw["findings"]:
        cit = Citation(
            url=f["citation"]["url"],
            title=f["citation"].get("title", ""),
            kind=f["citation"].get("kind", ""),
            metadata=dict(f["citation"].get("metadata") or {}),
        )
        findings.append(
            Finding(
                summary=f["summary"],
                citation=cit,
                excerpt=f.get("excerpt", ""),
            )
        )

    class _R:
        pass

    r = _R()
    r.findings = findings  # type: ignore[attr-defined]
    return r


async def test_legacy_result_yields_only_no_record_verdicts() -> None:
    raw = json.loads(FIXTURE.read_text(encoding="utf-8"))
    wrapped = _hydrate(raw)
    fetcher = _CountingFetcher()
    validator = ProvenanceValidator(fetcher=fetcher)

    report = await validator.check_agent_output(wrapped)

    assert len(report.verdicts) == 2
    assert all(v.status == "no_record" for v in report.verdicts)
    assert fetcher.calls == []
    assert report.summary["no_record"] == 2


async def test_mixed_legacy_and_new_findings_coexist() -> None:
    """Half-and-half result: legacy citations skip, new ones get checked."""

    from jw_core.provenance.hashing import content_sha256

    body_new = "new finding body"
    findings = [
        Finding(
            summary="legacy",
            citation=Citation(url="https://wol.jw.org/legacy", metadata={}),
            excerpt="",
        ),
        Finding(
            summary="new",
            citation=Citation(
                url="https://wol.jw.org/new",
                metadata={
                    "accessed_at": "2026-05-30T10:00:00Z",
                    "content_hash": content_sha256(body_new),
                },
            ),
            excerpt=body_new,
        ),
    ]

    class _R:
        pass

    r = _R()
    r.findings = findings  # type: ignore[attr-defined]

    class _F:
        calls: list[str] = []

        async def __call__(self, url: str) -> FetcherResponse:
            _F.calls.append(url)
            return FetcherResponse(final_url=url, status=200, body=body_new)

    fetcher = _F()
    validator = ProvenanceValidator(fetcher=fetcher)
    report = await validator.check_agent_output(r)

    statuses = [v.status for v in report.verdicts]
    assert "no_record" in statuses
    assert "match" in statuses
    assert fetcher.calls == ["https://wol.jw.org/new"]


def test_provenance_record_from_legacy_metadata_returns_none() -> None:
    """Unit-level confirmation: legacy metadata dict can't fool the projection."""

    from jw_core.provenance.models import ProvenanceRecord

    assert ProvenanceRecord.from_citation_metadata({"source": "wol"}) is None
    assert ProvenanceRecord.from_citation_metadata({}) is None
