"""``jw apologetics`` — answer doctrinal questions with verified citations.

Wraps the ``apologetics`` agent (jw-agents) and surfaces the new Fase 39
``--fidelity`` flag (off | warn | reject) which enables runtime NLI
verification of every Finding before printing.

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

Fidelity = Literal["off", "warn", "reject"]


def apologetics_cmd(
    question: str = typer.Argument(..., help="Doctrinal question to answer."),
    language: str = typer.Option("E", "--language", "-l", help="Language code (E, S, P, ...)."),
    fidelity: Fidelity = typer.Option(
        "warn",
        "--fidelity",
        help="NLI runtime verification: off (skip) | warn (annotate + warn) | "
        "reject (drop low-fidelity findings). Default: warn.",
        case_sensitive=False,
    ),
) -> None:
    """Answer an apologetics question with cited findings, NLI-verified by default."""

    if fidelity == "off":
        callable_agent = apologetics
    else:
        callable_agent = fidelity_wrap(
            min_score=0.7,
            on_fail="reject" if fidelity == "reject" else "warn",
        )(apologetics)

    result = asyncio.run(callable_agent(question=question, language=language))
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
