"""``jw reason`` - doctrinal chain-of-thought reasoner (Fase 67)."""

from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import Any

import typer
from rich.console import Console

from jw_agents.reasoner.engine import doctrinal_reasoner
from jw_agents.reasoner.models import ReasonerConfig

reason_app = typer.Typer(
    help="Razonador doctrinal con árbol verificable (Fase 67).",
    no_args_is_help=True,
)
console = Console()


def _build_llm() -> Any:
    """Bridge JW_REASONER_LLM to JW_META_LLM via F65 factory."""

    backend = os.environ.get("JW_REASONER_LLM", "fake").lower()
    if backend in ("", "fake"):

        import json as _json

        class _FakeLLM:
            name = "fake"

            async def acomplete(self, prompt: str) -> str:  # noqa: ARG002
                return _json.dumps({"steps": []})

        return _FakeLLM()
    try:
        from jw_agents.meta.llm_factory import build_llm_from_env

        os.environ.setdefault("JW_META_LLM", backend)
        return build_llm_from_env()
    except Exception as exc:  # noqa: BLE001
        console.print(
            f"[yellow]reasoner: backend {backend!r} unavailable ({exc}); "
            "using fake.[/]"
        )

        import json as _json

        class _FakeLLM:
            name = "fake"

            async def acomplete(self, prompt: str) -> str:  # noqa: ARG002
                return _json.dumps({"steps": []})

        return _FakeLLM()


def _build_nli(language: str) -> Any | None:
    """Resolve NLI via F65 nli_factory."""
    try:
        from jw_agents.meta.nli_factory import build_nli_from_env

        return build_nli_from_env(language=language)
    except Exception:
        return None


@reason_app.command("languages")
def cmd_languages() -> None:
    """List languages supported by the reasoner prompts."""
    console.print("es, en, pt")


@reason_app.command("ask")
def cmd_ask(
    question: str = typer.Argument(...),
    language: str = typer.Option("es", "--language", "-l"),
    max_steps: int = typer.Option(12, "--max-steps"),
    nli_mode: str = typer.Option(
        "reject", "--nli-mode", help="off | warn | reject"
    ),
    no_reformulate: bool = typer.Option(
        False, "--no-reformulate", help="Skip toxic framing rewrite."
    ),
    no_summary: bool = typer.Option(
        False, "--no-summary", help="Skip prose summary."
    ),
    export_md: str | None = typer.Option(
        None, "--export", help="Export the tree as Markdown."
    ),
) -> None:
    """Reason step-by-step and print the verifiable tree."""

    cfg = ReasonerConfig(
        language=language,  # type: ignore[arg-type]
        max_steps=max_steps,
        nli_mode=nli_mode,  # type: ignore[arg-type]
        reformulate_toxic=not no_reformulate,
        include_summary_prose=not no_summary,
    )
    llm = _build_llm()
    nli = _build_nli(language)
    tree = asyncio.run(
        doctrinal_reasoner(
            question=question, llm=llm, config=cfg, nli=nli
        )
    )
    console.print_json(tree.model_dump_json())

    if export_md:
        out = Path(export_md).expanduser()
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(_to_markdown(tree))
        console.print(f"[dim]tree exported to[/] {out}")


def _to_markdown(tree: Any) -> str:
    lines = [
        f"# Doctrinal reasoning: {tree.question_original}",
        "",
        f"- Normalized question: {tree.question_normalized}",
        f"- Truncated: {tree.truncated}",
        f"- NLI provider: {tree.nli_provider_used or 'none'}",
        "",
        "## Steps",
        "",
    ]
    for step in tree.steps:
        lines.append(
            f"### {step.id} ({step.kind}) - NLI: {step.nli_status}"
        )
        lines.append("")
        lines.append(f"**Statement**: {step.statement}")
        if step.rationale:
            lines.append("")
            lines.append(f"**Rationale**: {step.rationale}")
        if step.citation:
            lines.append("")
            lines.append(
                f"**Cite**: [{step.citation.source_kind}]"
                f"({step.citation.wol_url}) - "
                f"\"{step.citation.text}\""
            )
        if step.rejected_reason:
            lines.append("")
            lines.append(f"**Rejected**: {step.rejected_reason}")
        lines.append("")

    if tree.summary_prose:
        lines.append("## Summary")
        lines.append("")
        lines.append(tree.summary_prose)
        lines.append("")
    return "\n".join(lines)
