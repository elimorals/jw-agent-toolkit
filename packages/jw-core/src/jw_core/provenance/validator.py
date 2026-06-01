"""Re-fetch citations and compare content hashes.

The validator is intentionally narrow: it does not own a network client,
does not parse HTML on its own, and does not know about Fase 39 unless
an `nli_provider` is passed. This keeps it deterministic in tests and
trivially mockable in CI.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Protocol

from jw_agents.base import Citation
from jw_core.provenance.hashing import canonicalize_text, content_sha256
from jw_core.provenance.models import (
    ProvenanceRecord,
    ProvenanceReport,
    ProvenanceVerdict,
)


@dataclass
class FetcherResponse:
    """Minimal response carried back from the injected fetcher."""

    final_url: str
    status: int
    body: str = ""
    redirect_chain: list[str] = field(default_factory=list)


AsyncFetcher = Callable[[str], Awaitable[FetcherResponse]]
Extractor = Callable[[str], str]


class NLIProvider(Protocol):  # pragma: no cover — structural typing only
    async def evaluate_entailment(self, claim: str, premise: str) -> Any: ...


def _default_extractor(body: str) -> str:
    return body


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


class ProvenanceValidator:
    """Compare stored content hashes vs live re-fetches.

    Args:
        fetcher:     async URL -> FetcherResponse. Required.
        extractor:   sync HTML/body -> plain text. Defaults to identity.
        nli_provider: Fase 39's NLIProvider. When provided AND a verdict
                     is `changed`, re-runs entailment on the new text.
        concurrency: max parallel fetches (default 4 — matches Fase 23).
    """

    def __init__(
        self,
        *,
        fetcher: AsyncFetcher,
        extractor: Extractor | None = None,
        nli_provider: NLIProvider | None = None,
        concurrency: int = 4,
    ) -> None:
        self._fetcher = fetcher
        self._extractor = extractor or _default_extractor
        self._nli_provider = nli_provider
        self._concurrency = concurrency
        self._sem: asyncio.Semaphore | None = None

    def _get_sem(self) -> asyncio.Semaphore:
        if self._sem is None:
            self._sem = asyncio.Semaphore(self._concurrency)
        return self._sem

    async def check(self, citation: Citation) -> ProvenanceVerdict:
        """Re-fetch one citation's URL and compare content hashes."""

        recheck_at = _utcnow_iso()
        record = ProvenanceRecord.from_citation_metadata(citation.metadata)
        if record is None:
            return ProvenanceVerdict(
                url=citation.url,
                status="no_record",
                original_hash=None,
                current_hash=None,
                delta_chars=None,
                accessed_at_original=None,
                accessed_at_recheck=recheck_at,
                notes=["citation has no provenance metadata"],
            )

        try:
            async with self._get_sem():
                resp = await self._fetcher(citation.url)
        except Exception as exc:  # noqa: BLE001
            return ProvenanceVerdict(
                url=citation.url,
                status="unreachable",
                original_hash=record.content_hash,
                current_hash=None,
                delta_chars=None,
                accessed_at_original=record.accessed_at,
                accessed_at_recheck=recheck_at,
                notes=[f"fetcher raised: {exc!r}"],
            )

        if not (200 <= resp.status < 300):
            return ProvenanceVerdict(
                url=citation.url,
                status="unreachable",
                original_hash=record.content_hash,
                current_hash=None,
                delta_chars=None,
                accessed_at_original=record.accessed_at,
                accessed_at_recheck=recheck_at,
                notes=[f"non-2xx response: HTTP {resp.status}"],
            )

        plain = self._extractor(resp.body)
        current_hash = content_sha256(plain)
        canonical_current = canonicalize_text(plain)
        delta = abs(len(canonical_current)) if current_hash != record.content_hash else 0

        if current_hash == record.content_hash:
            return ProvenanceVerdict(
                url=citation.url,
                status="match",
                original_hash=record.content_hash,
                current_hash=current_hash,
                delta_chars=0,
                accessed_at_original=record.accessed_at,
                accessed_at_recheck=recheck_at,
            )

        verdict = ProvenanceVerdict(
            url=citation.url,
            status="changed",
            original_hash=record.content_hash,
            current_hash=current_hash,
            delta_chars=delta,
            accessed_at_original=record.accessed_at,
            accessed_at_recheck=recheck_at,
            notes=["sha256 mismatch"],
        )

        if self._nli_provider is not None:
            verdict.nli_rerun = await self._maybe_rerun_nli(citation, canonical_current)

        return verdict

    async def _maybe_rerun_nli(
        self,
        citation: Citation,
        new_premise: str,
    ) -> dict[str, Any] | None:
        """Re-run NLI on the new text and report a delta vs the stored verdict."""

        claim = citation.metadata.get("nli_claim")
        baseline = citation.metadata.get("nli_verdict")
        if not isinstance(claim, str) or not claim:
            return None
        try:
            new = await self._nli_provider.evaluate_entailment(claim, new_premise)
        except Exception as exc:  # noqa: BLE001
            return {"changed": False, "error": f"nli_rerun failed: {exc!r}"}
        new_label = getattr(new, "label", None)
        if new_label is None and isinstance(new, dict):
            new_label = new.get("label")
        new_score = getattr(new, "score", None)
        if new_score is None and isinstance(new, dict):
            new_score = new.get("score")
        if new_label is None:
            return None
        return {
            "changed": (baseline != new_label),
            "from": baseline,
            "to": new_label,
            "score": new_score,
        }

    async def check_agent_output(self, agent_output: Any) -> ProvenanceReport:
        """Iterate the result's findings, dedup by URL, parallelize fetches."""

        started = datetime.now(timezone.utc)
        citations = self._collect_citations(agent_output)
        verdicts = await self._check_many(citations)
        finished = datetime.now(timezone.utc)
        return ProvenanceReport(
            started_at=started,
            finished_at=finished,
            verdicts=verdicts,
            summary=ProvenanceReport.summarize(verdicts),
        )

    async def check_since(
        self,
        agent_output: Any,
        *,
        since: datetime,
    ) -> ProvenanceReport:
        """Like check_agent_output but skips citations younger than `since`."""

        started = datetime.now(timezone.utc)
        all_citations = self._collect_citations(agent_output)
        to_check: list[Citation] = []
        skipped_verdicts: list[ProvenanceVerdict] = []
        recheck_at = _utcnow_iso()
        for cit in all_citations:
            accessed = _parse_iso(cit.metadata.get("accessed_at"))
            if accessed is not None and accessed >= since:
                skipped_verdicts.append(
                    ProvenanceVerdict(
                        url=cit.url,
                        status="skipped",
                        original_hash=cit.metadata.get("content_hash"),
                        current_hash=None,
                        delta_chars=None,
                        accessed_at_original=cit.metadata.get("accessed_at"),
                        accessed_at_recheck=recheck_at,
                        notes=[f"accessed_at >= since={since.isoformat()}"],
                    )
                )
            else:
                to_check.append(cit)
        fetched = await self._check_many(to_check)
        verdicts = fetched + skipped_verdicts
        finished = datetime.now(timezone.utc)
        return ProvenanceReport(
            started_at=started,
            finished_at=finished,
            verdicts=verdicts,
            summary=ProvenanceReport.summarize(verdicts),
        )

    @staticmethod
    def _collect_citations(agent_output: Any) -> list[Citation]:
        """Best-effort: pull citations out of `findings`. Order preserved."""

        out: list[Citation] = []
        for f in getattr(agent_output, "findings", []) or []:
            cit = getattr(f, "citation", None)
            if isinstance(cit, Citation):
                out.append(cit)
        return out

    async def _check_many(self, citations: list[Citation]) -> list[ProvenanceVerdict]:
        """Dedup by URL, run checks concurrently, then re-expand by URL."""

        seen: dict[str, Citation] = {}
        order: list[str] = []
        for cit in citations:
            if cit.url not in seen:
                seen[cit.url] = cit
                order.append(cit.url)
        tasks = [self.check(seen[u]) for u in order]
        verdicts_by_url = dict(zip(order, await asyncio.gather(*tasks), strict=True))
        return [verdicts_by_url[c.url] for c in citations]
