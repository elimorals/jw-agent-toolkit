"""`jw constrained` — grammar-anchored LLM synthesis on top of any agent.

Fase 35 (constrained-decoding) — exposes `run_with_citations()` as a CLI
verb so operators can drive any registered agent through the GBNF-anchored
synthesis pipeline.

Usage:
    JW_LLM_PROVIDER=fake jw constrained ask --agent verse_explainer \
        --input '{"reference":"John 3:16","language":"en"}'
"""

from __future__ import annotations

import asyncio
import inspect
import json
from collections.abc import Awaitable, Callable
from typing import Any

import typer
from jw_agents.base import AgentResult
from jw_agents.constrained import run_with_citations
from jw_core.grammar.factory import get_default_constrained_caller

constrained_app = typer.Typer(
    name="constrained",
    help="LLM synthesis with grammar-anchored citations.",
    no_args_is_help=True,
)


@constrained_app.callback()
def _callback() -> None:
    """Grammar-anchored synthesis on top of procedural agents."""


# Mapping of common alias keys (LLM-facing) → real keyword arguments of
# the registered agents. Keeps the CLI input format stable even if
# individual agent signatures use slightly different field names.
_INPUT_ALIASES: dict[str, str] = {
    "reference": "text",
    "verse": "text",
    "verse_reference": "text",
    "query": "question",
    "topic": "question",
    "prompt": "question",
}


def _normalize_input(fn: Callable[..., Any], payload: dict[str, Any]) -> dict[str, Any]:
    """Drop unknown keys and remap aliases to the agent's real kwargs."""

    sig = inspect.signature(fn)
    valid = {
        name
        for name, p in sig.parameters.items()
        if p.kind
        in (
            inspect.Parameter.POSITIONAL_OR_KEYWORD,
            inspect.Parameter.KEYWORD_ONLY,
        )
    }
    out: dict[str, Any] = {}
    for k, v in payload.items():
        target = _INPUT_ALIASES.get(k, k)
        if target in valid:
            out[target] = v
    return out


def _agent_callable(
    name: str,
) -> Callable[[dict[str, Any]], Awaitable[AgentResult] | AgentResult]:
    """Resolve an agent by name into a (sync-or-async) callable.

    Raises `typer.BadParameter` (exit code != 0) when the name is unknown.
    """

    from jw_agents.apologetics import apologetics as _apologetics
    from jw_agents.conversation_assistant import (
        conversation_assistant as _conversation_assistant,
    )
    from jw_agents.meeting_helper import meeting_helper as _meeting_helper
    from jw_agents.research_topic import research_topic as _research_topic
    from jw_agents.verse_explainer import verse_explainer as _verse_explainer

    registry: dict[str, Callable[..., Any]] = {
        "apologetics": _apologetics,
        "conversation_assistant": _conversation_assistant,
        "meeting_helper": _meeting_helper,
        "research_topic": _research_topic,
        "verse_explainer": _verse_explainer,
    }
    if name not in registry:
        raise typer.BadParameter(f"unknown agent: {name!r} (have {sorted(registry)})")

    fn = registry[name]

    def call(inp: dict[str, Any]) -> Any:
        kwargs = _normalize_input(fn, inp)
        return fn(**kwargs)

    return call


@constrained_app.command("ask")
def ask(
    agent: str = typer.Option(..., "--agent", help="Agent name (e.g. verse_explainer)."),
    input_json: str = typer.Option("{}", "--input", help="JSON input for the agent."),
    provider: str = typer.Option(
        "auto",
        "--provider",
        help="auto | ollama | anthropic | openai | fake | llama-cpp",
    ),
    language: str = typer.Option("en", "--language"),
    temperature: float = typer.Option(0.3, "--temperature"),
) -> None:
    """Run the agent procedurally, then constrain an LLM to emit citation-anchored JSON."""

    payload = json.loads(input_json)
    agent_fn = _agent_callable(agent)

    caller = (
        None if provider == "auto" else get_default_constrained_caller(provider=provider)  # type: ignore[arg-type]
    )

    async def _run() -> AgentResult:
        return await run_with_citations(
            prompt=json.dumps(payload, ensure_ascii=False),
            # Ignore the prompt-derived inp dict that run_with_citations
            # synthesizes; the operator already provided structured input.
            agent=lambda _inp: agent_fn(payload),
            caller=caller,
            language=language,
            temperature=temperature,
        )

    result = asyncio.run(_run())
    typer.echo(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
