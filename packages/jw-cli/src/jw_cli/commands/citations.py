"""`jw citations` — verify integrity of wol.jw.org URLs.

Subcommands:
    jw citations check --urls urls.txt
    jw citations check --agent-output result.json
    jw citations check --urls urls.txt --live
    jw citations check --urls urls.txt --live --drift
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import typer
from rich.console import Console

from jw_core.citations import CitationValidator
from jw_core.integrations.meps_catalog import MepsCatalog

console = Console()
citations_app = typer.Typer(
    name="citations",
    help="Verify wol.jw.org citation integrity (HTTP + MEPS catalog + drift).",
    no_args_is_help=True,
)


@citations_app.callback()
def _callback() -> None:
    """Citation integrity tooling for wol.jw.org URLs."""
    # Forces Typer to keep `check` as a subcommand even when it's the only one.


@citations_app.command("check")
def check_cmd(
    urls_path: Path | None = typer.Option(
        None, "--urls", help="Path to a text file with one URL per line."
    ),
    agent_output_path: Path | None = typer.Option(
        None, "--agent-output", help="Path to a serialized AgentResult JSON."
    ),
    live: bool = typer.Option(False, "--live", help="Hit wol.jw.org over HTTP."),
    drift: bool = typer.Option(False, "--drift", help="Compare against committed snapshots."),
    snapshots_root: Path = typer.Option(
        Path("packages/jw-eval/fixtures/wol_snapshots"),
        "--snapshots-root",
        help="Snapshot directory (defaults to jw-eval's).",
    ),
    concurrency: int = typer.Option(4, "--concurrency", min=1, max=32),
    report_format: str = typer.Option("md", "--report", help="md | json"),
    out: Path | None = typer.Option(
        None, "--out", help="Write report to file instead of stdout."
    ),
) -> None:
    """Run the citation integrity validator."""

    if (urls_path is None) == (agent_output_path is None):
        raise typer.BadParameter("pass exactly one of --urls / --agent-output")

    if urls_path is not None:
        urls = [
            line.strip()
            for line in urls_path.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.startswith("#")
        ]
        agent_output = None
    else:
        urls = None
        assert agent_output_path is not None  # narrow for type-checkers
        agent_output = json.loads(agent_output_path.read_text(encoding="utf-8"))

    async def _run() -> dict:
        catalog = MepsCatalog()
        kwargs: dict = {"catalog": catalog, "concurrency": concurrency}

        client = None
        if live:
            import httpx

            from jw_core.citations.validator import httpx_fetcher

            client = httpx.AsyncClient(timeout=30.0, follow_redirects=True)
            kwargs["fetcher"] = httpx_fetcher(client)

        if drift:
            kwargs["snapshots_root"] = snapshots_root

        v = CitationValidator(**kwargs)
        mode = "live+drift" if (live and drift) else ("live" if live else "structural")
        try:
            if urls is not None:
                report = await v.validate_urls(urls, mode=mode)
            else:
                report = await v.validate_agent_output(agent_output, mode=mode)
            return report.model_dump(mode="json")
        finally:
            if client is not None:
                await client.aclose()

    report_dict = asyncio.run(_run())

    if report_format == "json":
        text = json.dumps(report_dict, indent=2, ensure_ascii=False)
    else:
        text = _to_markdown(report_dict)

    if out:
        out.write_text(text, encoding="utf-8")
        console.print(f"Wrote {out}")
    else:
        # Use print() not console.print() so output captures cleanly for tests.
        print(text)

    failed = report_dict["summary"]["failed"]
    raise typer.Exit(code=min(int(failed), 125))


def _to_markdown(report: dict) -> str:
    lines: list[str] = []
    lines.append("# Citation integrity report")
    lines.append("")
    lines.append(f"- **Mode:** `{report['mode']}`")
    s = report["summary"]
    lines.append(
        f"- **Summary:** total={s['total']} · ok={s['ok']} · "
        f"warning={s['warning']} · failed={s['failed']}"
    )
    lines.append("")
    lines.append("| URL | resolve | catalog | drift | notes |")
    lines.append("|---|---|---|---|---|")
    for c in report["checks"]:
        notes = "; ".join(c.get("notes") or []) or "—"
        lines.append(
            f"| `{c['url']}` | {c['resolve']} | {c['catalog']} | {c['drift']} | {notes} |"
        )
    return "\n".join(lines) + "\n"
