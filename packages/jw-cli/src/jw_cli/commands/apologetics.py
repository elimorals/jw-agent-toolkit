"""``jw apologetics`` — answer doctrinal questions with verified citations.

Wraps the ``apologetics`` agent (jw-agents) and surfaces:
  - ``--fidelity`` (Fase 39): NLI runtime verification of every Finding
  - ``--trace`` (Fase 43): emit a structured JSONL trace of every internal
    decision (kept / dropped / warn) to a file, stdout, or the default dir.

The CLI prints the structured JSON result so calling LLMs (Claude Desktop,
etc.) can synthesize prose with citations.
"""

from __future__ import annotations

import asyncio
import json
from typing import Literal

import typer
from jw_agents.apologetics import apologetics
from jw_agents.fidelity_wrap import fidelity_wrap
from jw_agents.tracing import use_tracer
from jw_agents.tracing._flag import resolve_trace_target, tracer_from_target

Fidelity = Literal["off", "warn", "reject"]


def apologetics_cmd(
    question: str = typer.Argument(..., help="Doctrinal question to answer."),
    language: str = typer.Option(
        "E", "--language", "-l", help="Language code (E, S, P, ...)."
    ),
    fidelity: Fidelity = typer.Option(
        "warn",
        "--fidelity",
        help="NLI runtime verification: off (skip) | warn (annotate + warn) | "
        "reject (drop low-fidelity findings). Default: warn.",
        case_sensitive=False,
    ),
    trace: str = typer.Option(
        None,
        "--trace",
        help=(
            "Emit a JSONL trace. Pass a path, '-' for stdout, or 'DEFAULT' "
            "for an auto-named file under $JW_TRACE_DIR."
        ),
    ),
) -> None:
    """Answer an apologetics question with cited findings, NLI-verified by default."""

    target = (
        resolve_trace_target(trace, agent="apologetics")
        if trace is not None
        else None
    )
    tracer = tracer_from_target(target, agent="apologetics")

    async def _run() -> object:
        if fidelity == "off":
            callable_agent = apologetics
        else:
            callable_agent = fidelity_wrap(
                min_score=0.7,
                on_fail="reject" if fidelity == "reject" else "warn",
            )(apologetics)
        # Bind the tracer as the ambient one so apologetics picks it up via
        # get_active_tracer even when fidelity_wrap stands between us.
        with use_tracer(tracer), tracer.run(
            input_kwargs={"question": question}, language=language
        ):
            return await callable_agent(question=question, language=language)

    result = asyncio.run(_run())
    typer.echo(
        json.dumps(
            {
                "query": result.query,
                "agent_name": result.agent_name,
                "findings": [
                    {
                        "summary": f.summary,
                        "excerpt": f.excerpt,
                        "citation": {
                            "url": f.citation.url,
                            "title": f.citation.title,
                            "kind": f.citation.kind,
                            "metadata": f.citation.metadata,
                        },
                        "metadata": f.metadata,
                    }
                    for f in result.findings
                ],
                "warnings": result.warnings,
                "metadata": result.metadata,
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    if target is not None and target != "-":
        typer.echo(f"trace written: {target}", err=True)
        typer.echo(f"trace_id: {tracer.trace_id}", err=True)
