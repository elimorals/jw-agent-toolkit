"""MCP tool: verify_provenance.

Exposed via FastMCP from server.py. Accepts a serialized AgentResult
(dict) and optionally re-runs NLI on drifted citations.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from jw_agents.base import Citation, Finding
from jw_core.provenance.validator import ProvenanceValidator


def _hydrate(agent_output: dict[str, Any]) -> Any:
    """Convert a JSON-serialized AgentResult into a Citation-bearing wrapper."""

    findings: list[Finding] = []
    for f in agent_output.get("findings", []) or []:
        cit_raw = f.get("citation") or {}
        cit = Citation(
            url=cit_raw.get("url", ""),
            title=cit_raw.get("title", ""),
            kind=cit_raw.get("kind", ""),
            metadata=dict(cit_raw.get("metadata") or {}),
        )
        findings.append(
            Finding(
                summary=f.get("summary", ""),
                citation=cit,
                excerpt=f.get("excerpt", "") or "",
                metadata=dict(f.get("metadata") or {}),
            )
        )

    class _R:
        pass

    r = _R()
    r.findings = findings  # type: ignore[attr-defined]
    return r


async def verify_provenance(
    agent_output: dict[str, Any],
    *,
    since: str | None = None,
    with_nli: bool = False,
    fetcher: Any | None = None,
    nli_provider: Any | None = None,
) -> dict[str, Any]:
    """Re-check that each citation's content_hash still matches the live page.

    Args:
        agent_output: serialized AgentResult dict (`AgentResult.to_dict()` shape).
        since: optional ISO date; only re-check citations accessed earlier.
        with_nli: hint that the caller wants NLI re-validation. No-op if
            no `nli_provider` wired.
        fetcher: injectable for tests; default constructed by server.py.
        nli_provider: injectable NLIProvider from Fase 39.
    """

    if fetcher is None:
        from jw_cli.commands.provenance import _HttpxFetcher  # type: ignore[import-not-found]

        fetcher = _HttpxFetcher()

    effective_nli = nli_provider if with_nli else None
    validator = ProvenanceValidator(fetcher=fetcher, nli_provider=effective_nli)
    wrapped = _hydrate(agent_output)

    if since is None:
        report = await validator.check_agent_output(wrapped)
    else:
        cutoff = datetime.fromisoformat(since)
        if cutoff.tzinfo is None:
            cutoff = cutoff.replace(tzinfo=UTC)
        report = await validator.check_since(wrapped, since=cutoff)

    return report.model_dump(mode="json")
