"""``jw meta`` — meta-orchestrator over the 12+ existing agents (Fase 65).

Wraps `MetaOrchestrator` (jw-agents) and surfaces:
  - `jw meta tools` — list registered tools (builtin + Plugin SDK F41)
  - `jw meta plan "<goal>"` — print the orchestration plan only
  - `jw meta run "<goal>"` — plan + execute + critique
  - `jw plan-sunday` — preconfigured alias for the Sunday meeting goal

Post-MVP wiring:
  - LLM provider env-driven via `jw_agents.meta.llm_factory.build_llm_from_env`
  - NLI provider env-driven via `jw_agents.meta.nli_factory.build_nli_from_env`
  - Tracing F43 via `--trace path/` (file) or `--trace -` (stdout)
  - Persistence via `--save-plan path/` and `--save-result path/`
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import typer
from rich.console import Console
from rich.table import Table

from jw_agents.meta.builtin_tools import register_builtin_tools
from jw_agents.meta.llm_factory import build_llm_from_env
from jw_agents.meta.nli_factory import build_nli_from_env
from jw_agents.meta.orchestrator import MetaOrchestrator
from jw_agents.meta.registry import discover_plugin_tools, list_tools

meta_app = typer.Typer(
    help="Meta orchestrator over JW agents (Fase 65).",
    no_args_is_help=True,
)

console = Console()


def _build_tracer(trace: str | None) -> Any | None:
    """Build an AgentTracer from a CLI --trace flag.

    `--trace path.jsonl` -> JsonlTraceStore at that path.
    `--trace -`          -> stdout via InMemoryTraceStore + print on exit
                            (kept simple: in-memory; the orchestrator emits
                            CustomEvents which we won't dump here).
    `--trace <dir>/`     -> auto-name file inside dir.
    """

    if trace is None:
        return None
    from jw_agents.tracing.store import InMemoryTraceStore, JsonlTraceStore
    from jw_agents.tracing.tracer import AgentTracer

    if trace == "-":
        return AgentTracer(agent="meta", store=InMemoryTraceStore())

    p = Path(trace).expanduser()
    if p.is_dir() or trace.endswith("/"):
        p.mkdir(parents=True, exist_ok=True)
        from datetime import UTC, datetime

        ts = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        p = p / f"meta-{ts}.jsonl"
    else:
        p.parent.mkdir(parents=True, exist_ok=True)
    return AgentTracer(agent="meta", store=JsonlTraceStore(p))


def _build_orchestrator(
    *,
    max_steps: int,
    max_replans: int,
    timeout_s: float,
    language: str = "en",
    trace: str | None = None,
) -> tuple[MetaOrchestrator, Any | None]:
    tracer = _build_tracer(trace)
    return (
        MetaOrchestrator(
            llm=build_llm_from_env(),
            nli=build_nli_from_env(language=language),
            max_steps=max_steps,
            max_replans=max_replans,
            timeout_s=timeout_s,
            tracer=tracer,
        ),
        tracer,
    )


def _maybe_save_json(payload_json: str, path: str | None, label: str) -> None:
    if not path:
        return
    out = Path(path).expanduser()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(payload_json)
    console.print(f"[dim]{label} saved to[/] {out}")


@meta_app.command("tools")
def cmd_tools() -> None:
    """List all registered tools (builtin + discovered plugins)."""

    register_builtin_tools()
    n_plugins = discover_plugin_tools()
    table = Table(title=f"Meta tools (builtin + {n_plugins} plugin)")
    table.add_column("Name")
    table.add_column("Description")
    for t in list_tools():
        table.add_row(t.name, t.description)
    console.print(table)


@meta_app.command("plan")
def cmd_plan(
    goal: str = typer.Argument(..., help="Goal description"),
    language: str = typer.Option("es", "--language", "-l"),
    congregation: str | None = typer.Option(None, "--congregation", "-c"),
    max_steps: int = typer.Option(8, "--max-steps"),
    save_plan: str | None = typer.Option(
        None, "--save-plan", help="Write OrchestrationPlan JSON to this path."
    ),
    mermaid: str | None = typer.Option(
        None,
        "--mermaid",
        help="Also write a Mermaid flowchart of the DAG to this path.",
    ),
) -> None:
    """Print the orchestration plan WITHOUT running it."""

    register_builtin_tools()
    discover_plugin_tools()
    orch, _ = _build_orchestrator(
        max_steps=max_steps, max_replans=0, timeout_s=30.0, language=language
    )
    plan = asyncio.run(
        orch.plan_only(
            goal=goal, language=language, congregation=congregation
        )
    )
    plan_json = plan.model_dump_json(indent=2)
    console.print_json(plan_json)
    _maybe_save_json(plan_json, save_plan, "plan")
    if mermaid:
        from jw_agents.meta.mermaid import plan_to_mermaid

        out = Path(mermaid).expanduser()
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(plan_to_mermaid(plan))
        console.print(f"[dim]mermaid saved to[/] {out}")


@meta_app.command("replay")
def cmd_replay(
    plan_path: str = typer.Argument(..., help="Path to a saved OrchestrationPlan JSON."),
    max_replans: int = typer.Option(0, "--max-replans"),
    timeout_s: float = typer.Option(120.0, "--timeout-s"),
    trace: str | None = typer.Option(None, "--trace"),
    save_result: str | None = typer.Option(None, "--save-result"),
) -> None:
    """Re-execute a plan previously saved via `--save-plan`."""

    import json
    from jw_agents.meta.models import OrchestrationPlan

    register_builtin_tools()
    discover_plugin_tools()
    payload = json.loads(Path(plan_path).expanduser().read_text())
    plan = OrchestrationPlan.model_validate(payload)
    orch, tracer = _build_orchestrator(
        max_steps=max(len(plan.steps), 8),
        max_replans=max_replans,
        timeout_s=timeout_s,
        language=plan.language,
        trace=trace,
    )

    async def _run() -> Any:
        if tracer is None:
            return await orch.run_plan(plan)
        with tracer.run(
            input_kwargs={"replay": plan_path}, language=plan.language
        ):
            return await orch.run_plan(plan)

    result = asyncio.run(_run())
    result_json = result.model_dump_json(indent=2)
    console.print_json(result_json)
    _maybe_save_json(result_json, save_result, "result")


@meta_app.command("run")
def cmd_run(
    goal: str = typer.Argument(..., help="Goal description"),
    language: str = typer.Option("es", "--language", "-l"),
    congregation: str | None = typer.Option(None, "--congregation", "-c"),
    max_steps: int = typer.Option(8, "--max-steps"),
    max_replans: int = typer.Option(2, "--max-replans"),
    timeout_s: float = typer.Option(120.0, "--timeout-s"),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Only print plan; do not execute"
    ),
    trace: str | None = typer.Option(
        None,
        "--trace",
        help='JSONL trace path. Use "-" for in-memory, or a directory to auto-name.',
    ),
    save_plan: str | None = typer.Option(
        None, "--save-plan", help="Write OrchestrationPlan JSON to this path."
    ),
    save_result: str | None = typer.Option(
        None,
        "--save-result",
        help="Write OrchestrationResult JSON to this path.",
    ),
) -> None:
    """Plan + execute + critique."""

    register_builtin_tools()
    discover_plugin_tools()
    orch, tracer = _build_orchestrator(
        max_steps=max_steps,
        max_replans=max_replans,
        timeout_s=timeout_s,
        language=language,
        trace=trace,
    )
    if dry_run:
        plan = asyncio.run(
            orch.plan_only(
                goal=goal, language=language, congregation=congregation
            )
        )
        plan_json = plan.model_dump_json(indent=2)
        console.print_json(plan_json)
        _maybe_save_json(plan_json, save_plan, "plan")
        return

    # Wrap the run in the tracer's run() so the JSONL envelope flushes correctly.
    async def _run() -> Any:
        if tracer is None:
            return await orch.run(
                goal=goal, language=language, congregation=congregation
            )
        with tracer.run(
            input_kwargs={"goal": goal, "language": language},
            language=language,
        ):
            return await orch.run(
                goal=goal, language=language, congregation=congregation
            )

    result = asyncio.run(_run())
    result_json = result.model_dump_json(indent=2)
    console.print_json(result_json)
    _maybe_save_json(result.plan.model_dump_json(indent=2), save_plan, "plan")
    _maybe_save_json(result_json, save_result, "result")


def plan_sunday_cmd(
    language: str = typer.Option("es", "--language", "-l"),
    congregation: str | None = typer.Option(None, "--congregation", "-c"),
    trace: str | None = typer.Option(None, "--trace"),
    save_result: str | None = typer.Option(None, "--save-result"),
) -> None:
    """Preconfigured alias for `jw plan-sunday`."""

    cmd_run(
        goal=(
            "Prepara mi reunión del domingo"
            if language == "es"
            else "Prepare my Sunday meeting"
        ),
        language=language,
        congregation=congregation,
        max_steps=8,
        max_replans=2,
        timeout_s=120.0,
        dry_run=False,
        trace=trace,
        save_plan=None,
        save_result=save_result,
    )
