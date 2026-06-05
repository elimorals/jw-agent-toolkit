"""CLI subcommand: `jw provenance ...` (Fase 40).

Exit codes:
  0 — every verdict is `match`, `skipped`, or `no_record`.
  2 — at least one verdict is `changed`.
  3 — at least one `unreachable` AND no `changed`.

Fetcher chosen via JW_PROVENANCE_FETCHER env var: unset/httpx (live),
`fake` (echoes excerpt back), `fake-drift` (always differs — test only).
"""

from __future__ import annotations

import asyncio
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import typer
from jw_agents.base import Citation, Finding
from jw_core.provenance.validator import FetcherResponse, ProvenanceValidator

provenance_app = typer.Typer(help="Content provenance checks.")


def _load_citations(path: Path) -> list[Citation]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    cits: list[Citation] = []
    for f in raw.get("findings", []):
        cit_raw = f.get("citation") or {}
        cits.append(
            Citation(
                url=cit_raw.get("url", ""),
                title=cit_raw.get("title", ""),
                kind=cit_raw.get("kind", ""),
                metadata=dict(cit_raw.get("metadata") or {}),
            )
        )
    return cits


def _wrap_as_result(citations: list[Citation]) -> Any:
    findings = [Finding(summary="", citation=c, excerpt="") for c in citations]

    class _R:
        pass

    r = _R()
    r.findings = findings  # type: ignore[attr-defined]
    return r


def _select_fetcher() -> Any:
    choice = os.environ.get("JW_PROVENANCE_FETCHER", "httpx").lower()
    if choice == "fake":
        return _FakeEchoFetcher()
    if choice == "fake-drift":
        return _FakeDriftFetcher()
    return _HttpxFetcher()


class _FakeEchoFetcher:
    """Returns the stored excerpt for each URL — used in tests for match path."""

    excerpts: dict[str, str] = {}

    async def __call__(self, url: str) -> FetcherResponse:
        body = _FakeEchoFetcher.excerpts.get(url, "")
        return FetcherResponse(final_url=url, status=200, body=body)


class _FakeDriftFetcher:
    async def __call__(self, url: str) -> FetcherResponse:
        return FetcherResponse(
            final_url=url, status=200, body="DRIFT_SENTINEL_TEXT"
        )


class _HttpxFetcher:
    """Real-network fetcher backed by httpx."""

    async def __call__(self, url: str) -> FetcherResponse:
        import httpx

        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            resp = await client.get(url, headers={"User-Agent": "jw-cli/provenance"})
            return FetcherResponse(
                final_url=str(resp.url),
                status=resp.status_code,
                body=resp.text,
                redirect_chain=[str(h.url) for h in resp.history],
            )


def _render_markdown(report) -> str:
    lines = [
        "# Provenance report",
        "",
        f"- started_at: {report.started_at.isoformat()}",
        f"- finished_at: {report.finished_at.isoformat()}",
        f"- summary: {report.summary}",
        "",
        "| URL | Status | Original hash | Current hash | Delta chars | Accessed (orig) | Accessed (recheck) |",
        "|-----|--------|---------------|--------------|-------------|-----------------|--------------------|",
    ]
    for v in report.verdicts:
        lines.append(
            f"| {v.url} | {v.status} | {v.original_hash or '-'} | {v.current_hash or '-'} "
            f"| {v.delta_chars if v.delta_chars is not None else '-'} "
            f"| {v.accessed_at_original or '-'} | {v.accessed_at_recheck} |"
        )
    return "\n".join(lines) + "\n"


def _exit_code(report) -> int:
    if report.summary.get("changed", 0) > 0:
        return 2
    if report.summary.get("unreachable", 0) > 0:
        return 3
    return 0


@provenance_app.command("check")
def check_cmd(
    agent_output: Path = typer.Option(..., "--agent-output", help="Path to an AgentResult JSON file."),
    since: str | None = typer.Option(None, "--since", help="ISO date — only re-check citations accessed before this date."),
    report: str = typer.Option("json", "--report", help="Output format: json or md."),
    out: Path | None = typer.Option(None, "--out", help="Optional output file path (default stdout)."),
) -> None:
    """Re-check that every citation's content_hash still matches the live source."""

    citations = _load_citations(agent_output)

    raw = json.loads(agent_output.read_text(encoding="utf-8"))
    excerpts: dict[str, str] = {}
    for f in raw.get("findings", []):
        cit = f.get("citation") or {}
        url = cit.get("url")
        excerpt = f.get("excerpt") or ""
        if url and excerpt:
            excerpts[url] = excerpt
    _FakeEchoFetcher.excerpts.update(excerpts)

    fetcher = _select_fetcher()
    validator = ProvenanceValidator(fetcher=fetcher)
    wrapped = _wrap_as_result(citations)

    async def run() -> Any:
        if since is None:
            return await validator.check_agent_output(wrapped)
        try:
            cutoff = datetime.fromisoformat(since)
            if cutoff.tzinfo is None:
                cutoff = cutoff.replace(tzinfo=UTC)
        except ValueError as exc:
            raise typer.BadParameter(f"--since must be ISO 8601: {exc}") from exc
        return await validator.check_since(wrapped, since=cutoff)

    result = asyncio.run(run())

    if report == "md":
        payload = _render_markdown(result)
    else:
        payload = result.model_dump_json()

    if out is not None:
        out.write_text(payload, encoding="utf-8")
    else:
        typer.echo(payload)

    raise typer.Exit(code=_exit_code(result))
