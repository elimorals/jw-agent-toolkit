"""jw-finetune CLI — entry-point for prepare, train, eval, export, run, presets, init.

All commands work without GPU extras except `train`, `evaluate`, and `export`,
which lazy-import Unsloth and fail with a clear ImportError if the relevant
extra (`--extra cuda`/`--extra mlx`/`--extra rocm`) is not installed.
"""

from __future__ import annotations

import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from jw_finetune.data.chunk import records_to_chunks
from jw_finetune.data.dedupe import deduplicate
from jw_finetune.data.extract import extract_from_epub, extract_from_jwpub
from jw_finetune.data.formats import write_raw_jsonl, write_sharegpt_jsonl
from jw_finetune.data.models import ParagraphRecord
from jw_finetune.recipes.base import (
    Recipe,
    recipe_from_yaml,
    recipe_to_yaml,
    validate_recipe,
)
from jw_finetune.recipes.presets import get_preset, list_presets

app = typer.Typer(
    no_args_is_help=True,
    add_completion=False,
    help="jw-finetune — local LLM fine-tuning for JW publications.",
)
console = Console()
logging.basicConfig(level=os.environ.get("JW_FT_LOGLEVEL", "INFO"))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_recipe(preset: str | None, recipe_file: Path | None) -> Recipe:
    if recipe_file:
        return recipe_from_yaml(recipe_file)
    if preset:
        return get_preset(preset)
    raise typer.BadParameter("Either --recipe (preset name) or --recipe-file is required")


def _new_run_dir(base: Path) -> Path:
    rid = datetime.now().strftime("run-%Y%m%d-%H%M%S")
    p = Path(base) / rid
    p.mkdir(parents=True, exist_ok=True)
    return p


def _latest_run_dir(base: Path) -> Path:
    """Return the most recent run-* directory under `base`."""
    runs = sorted(d for d in base.iterdir() if d.is_dir() and d.name.startswith("run-"))
    if not runs:
        raise typer.BadParameter(f"No run-* directory found under {base}")
    return runs[-1]


def _iter_source_paths(p: Path):
    """Expand a path into individual JWPUB/EPUB files (recursive for dirs)."""
    if p.is_dir():
        yield from sorted(p.rglob("*.jwpub"))
        yield from sorted(p.rglob("*.epub"))
    else:
        yield p


def _build_provider(provider_name: str | None, model_name: str | None):
    name = (provider_name or "ollama").lower()
    if name == "ollama":
        from jw_finetune.synth.ollama_provider import OllamaProvider

        return OllamaProvider(model=model_name or "llama3.1:8b")
    if name == "anthropic":
        from jw_finetune.synth.anthropic_provider import AnthropicProvider

        return AnthropicProvider(model=model_name or "claude-haiku-4-5-20251001")
    raise typer.BadParameter(f"Unknown synth provider: {name!r}")


def _extract_all(sources: list[Path], language_hint: str) -> list[ParagraphRecord]:
    records: list[ParagraphRecord] = []
    for src in sources:
        for p in _iter_source_paths(src):
            suffix = p.suffix.lower()
            console.print(f"[dim]Extracting {p}[/dim]")
            try:
                if suffix == ".epub":
                    records.extend(extract_from_epub(p, language_hint=language_hint))
                elif suffix == ".jwpub":
                    records.extend(extract_from_jwpub(p, language_hint=language_hint))
                else:
                    console.print(f"[yellow]Skipping unknown format: {p}[/yellow]")
            except Exception as e:  # noqa: BLE001
                console.print(f"[red]Failed to extract {p}: {e}[/red]")
    return records


def _synth_chunks(chunks, provider, rec: Recipe):
    """Synthesize Q&A using the async orchestrator + rich progress bar."""
    import asyncio

    from jw_finetune.synth.async_orchestrator import synthesize_chunks_async
    from jw_finetune.ux.progress import synth_progress_bar

    # Concurrency policy: Anthropic ~10 parallel requests safely; Ollama
    # ~4 on a single-GPU machine before queueing.
    concurrency = 10 if getattr(provider, "name", "") == "anthropic" else 4

    async def _run():
        chunks_list = list(chunks)
        with synth_progress_bar(len(chunks_list)) as (_tid, advance):
            res = await synthesize_chunks_async(
                chunks_list,
                provider=provider,
                qa_style=rec.qa_style or "doctrinal",
                language=rec.languages[0],
                n_pairs=rec.qa_per_chunk,
                concurrency=concurrency,
                progress=lambda done, total, pairs: advance(pairs),
            )
        console.print(
            f"[dim]Cache hits: {res.cache_hits}, "
            f"misses: {res.cache_misses}, "
            f"rejected pairs: {res.total_rejected}, "
            f"parse errors: {res.parse_errors}[/dim]"
        )
        return res.pairs

    return asyncio.run(_run())


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------


@app.command()
def presets() -> None:
    """List built-in recipe presets."""
    table = Table(title="jw-finetune presets")
    table.add_column("Name", style="cyan")
    table.add_column("Task", style="magenta")
    table.add_column("Languages", style="green")
    table.add_column("Base model", style="yellow")
    table.add_column("QA style", style="white")
    for name in list_presets():
        r = get_preset(name)
        table.add_row(name, r.task, ",".join(r.languages), r.base_model, r.qa_style or "-")
    console.print(table)


@app.command()
def init(
    preset: Annotated[str, typer.Option("--preset", "-p", help="Preset name to copy.")],
    out: Annotated[Path, typer.Option("--out", "-o")] = Path("./recipe.yaml"),
) -> None:
    """Write a recipe YAML from a preset."""
    r = get_preset(preset)
    recipe_to_yaml(r, out)
    console.print(f"[green]✓[/green] Recipe written to {out}")


@app.command()
def prepare(
    recipe: Annotated[str | None, typer.Option("--recipe", "-r", help="Preset name.")] = None,
    recipe_file: Annotated[Path | None, typer.Option("--recipe-file", help="Path to YAML recipe.")] = None,
    source: Annotated[
        list[Path] | None,
        typer.Option("--source", "-s", help="JWPUB/EPUB file or directory; may repeat."),
    ] = None,
    workspace: Annotated[Path, typer.Option("--workspace", "-w")] = Path("./jw-finetune-workspace"),
    provider: Annotated[
        str | None,
        typer.Option("--synth-provider", help="anthropic | ollama"),
    ] = None,
    model: Annotated[str | None, typer.Option("--synth-model")] = None,
) -> None:
    """Stage 1-4: extract → dedupe → chunk → (synth Q&A if SFT)."""
    rec = _load_recipe(recipe, recipe_file)
    errors = validate_recipe(rec)
    if errors:
        for e in errors:
            console.print(f"[red]✗ {e}[/red]")
        raise typer.Exit(2)

    source_paths = list(source or [])
    if not source_paths:
        console.print("[red]✗ At least one --source is required[/red]")
        raise typer.Exit(2)

    run_dir = _new_run_dir(workspace)
    console.print(f"[blue]Run dir:[/blue] {run_dir}")

    records = _extract_all(source_paths, rec.languages[0])
    console.print(f"[blue]Extracted:[/blue] {len(records)} paragraphs")
    if not records:
        console.print("[red]✗ No records extracted; aborting.[/red]")
        raise typer.Exit(3)

    deduped = list(deduplicate(records, threshold=rec.dedupe_threshold))
    console.print(f"[blue]After dedupe:[/blue] {len(deduped)}")

    chunks = records_to_chunks(deduped, max_chars=rec.max_chunk_chars, min_chars=rec.min_chunk_chars)
    console.print(f"[blue]Chunks:[/blue] {len(chunks)}")

    if rec.task == "cpt":
        out = run_dir / "dataset_raw.jsonl"
        n = write_raw_jsonl(chunks, out)
        console.print(f"[green]✓[/green] CPT dataset: {out} ({n} records)")
    else:
        prov = _build_provider(provider or rec.synth_provider, model or rec.synth_model)
        qas = _synth_chunks(chunks, prov, rec)
        out = run_dir / "dataset_qa.jsonl"
        n = write_sharegpt_jsonl(qas, out)
        console.print(f"[green]✓[/green] SFT dataset: {out} ({n} pairs)")

    recipe_to_yaml(rec, run_dir / "recipe.yaml")
    console.print(f"[green]✓[/green] Recipe saved: {run_dir / 'recipe.yaml'}")


@app.command()
def train(
    workspace: Annotated[Path, typer.Option("--workspace", "-w")],
    resume: Annotated[bool, typer.Option("--resume/--no-resume")] = False,
) -> None:
    """Run training (SFT, CPT, or GRPO depending on recipe.task)."""
    recipe_path = workspace / "recipe.yaml"
    if not recipe_path.exists():
        console.print(f"[red]✗ recipe.yaml not found in {workspace}[/red]")
        raise typer.Exit(2)

    rec = recipe_from_yaml(recipe_path)
    if rec.task == "cpt":
        from jw_finetune.train.cpt import train_cpt

        dataset = workspace / "dataset_raw.jsonl"
        final = train_cpt(rec, dataset, workspace, resume_from_checkpoint=resume or None)
    elif rec.task == "grpo":
        from jw_finetune.train.grpo import train_grpo

        # GRPO expects a dataset with a `prompt` field; reuse dataset_qa.jsonl
        # if present, otherwise dataset_raw.jsonl. The user is responsible
        # for ensuring the schema matches.
        for candidate in ("dataset_qa.jsonl", "dataset_raw.jsonl"):
            if (workspace / candidate).exists():
                dataset = workspace / candidate
                break
        else:
            console.print("[red]✗ No dataset found in workspace[/red]")
            raise typer.Exit(2)
        final = train_grpo(rec, dataset, workspace, resume_from_checkpoint=resume or None)
    else:
        from jw_finetune.train.sft import train_sft

        dataset = workspace / "dataset_qa.jsonl"
        final = train_sft(rec, dataset, workspace, resume_from_checkpoint=resume or None)
    console.print(f"[green]✓ Final checkpoint:[/green] {final}")


@app.command(name="evaluate")
def evaluate_cmd(
    checkpoint: Annotated[Path, typer.Option("--checkpoint", "-c")],
    prompts: Annotated[
        Path,
        typer.Option("--prompts", "-p", help="Text file with one prompt per line."),
    ],
    language: Annotated[str, typer.Option("--language", "-l")] = "es",
    out: Annotated[Path, typer.Option("--out", "-o")] = Path("./eval-report.json"),
) -> None:
    """Run evaluation on a checkpoint."""
    from jw_finetune.eval.runner import run_eval, write_eval_report

    prompt_list = [ln.strip() for ln in prompts.read_text(encoding="utf-8").splitlines() if ln.strip()]
    result = run_eval(checkpoint, prompt_list, language=language)
    write_eval_report(result, out)
    console.print(f"[green]✓ Eval report:[/green] {out}")
    console.print(f"  citation_accuracy = {result.citation_accuracy:.2%}")
    console.print(f"  terminology_score = {result.terminology_score:.2%}")


@app.command()
def export(
    checkpoint: Annotated[Path, typer.Option("--checkpoint", "-c")],
    fmt: Annotated[
        str,
        typer.Option(
            "--format",
            "-f",
            help="gguf | mlx | merged | adapter",
        ),
    ] = "gguf",
    quant: Annotated[str, typer.Option("--quant", "-q")] = "Q4_K_M",
    out: Annotated[Path, typer.Option("--out", "-o")] = Path("./export"),
    write_readme: Annotated[bool, typer.Option("--write-readme/--no-readme")] = True,
) -> None:
    """Export a trained checkpoint to GGUF/MLX/safetensors."""
    fmt_low = fmt.lower()
    if fmt_low == "gguf":
        from jw_finetune.export.gguf import export_gguf

        p = export_gguf(checkpoint, out, quant=quant)
    elif fmt_low == "mlx":
        from jw_finetune.export.mlx import export_mlx

        bits = "q4" if quant.lower().startswith("q4") else "q8"
        p = export_mlx(checkpoint, out, quant=bits)
    elif fmt_low == "merged":
        from jw_finetune.export.safetensors_export import export_merged

        p = export_merged(checkpoint, out)
    elif fmt_low == "adapter":
        from jw_finetune.export.safetensors_export import export_adapter_only

        p = export_adapter_only(checkpoint, out)
    else:
        raise typer.BadParameter(f"Unknown format: {fmt}")
    console.print(f"[green]✓ Exported:[/green] {p}")

    if write_readme:
        try:
            # checkpoint is `.../<run-dir>/checkpoints/final`; workspace is two up.
            workspace = checkpoint.parent.parent
            from jw_finetune.ux.run_readme import write_run_readme

            readme_path = write_run_readme(
                workspace=workspace,
                export_dir=p,
                export_format=fmt_low,
                quant=quant,
            )
            console.print(f"[green]✓ README:[/green] {readme_path}")
        except Exception as e:  # noqa: BLE001
            console.print(f"[yellow]README skipped:[/yellow] {e}")


@app.command()
def doctor() -> None:
    """Run health checks for jw-finetune (GPU, deps, Ollama, JW Library, workspace)."""
    from jw_finetune.ux.doctor import render_report, run_doctor

    report = run_doctor()
    console.print(render_report(report))
    if not report.ok:
        raise typer.Exit(1)


@app.command(name="diff")
def diff_cmd(
    checkpoint_a: Annotated[Path, typer.Option("--a", "-a")],
    checkpoint_b: Annotated[Path, typer.Option("--b", "-b")],
    prompts: Annotated[Path, typer.Option("--prompts", "-p")],
    language: Annotated[str, typer.Option("--language", "-l")] = "es",
    out: Annotated[Path, typer.Option("--out", "-o")] = Path("./diff-report.json"),
) -> None:
    """Compare two checkpoints by running the same prompts through each."""
    import json
    from dataclasses import asdict

    from jw_finetune.ux.diff import compare_checkpoints

    prompt_list = [ln.strip() for ln in prompts.read_text(encoding="utf-8").splitlines() if ln.strip()]
    result = compare_checkpoints(
        checkpoint_a,
        checkpoint_b,
        prompt_list,
        language=language,
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(
            {
                "checkpoint_a": result.checkpoint_a,
                "checkpoint_b": result.checkpoint_b,
                "mean_citation_a": result.mean_citation_a,
                "mean_citation_b": result.mean_citation_b,
                "mean_terminology_a": result.mean_terminology_a,
                "mean_terminology_b": result.mean_terminology_b,
                "rows": [asdict(r) for r in result.rows],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    console.print(f"[green]✓ Diff report:[/green] {out}")
    console.print(f"  A: citation {result.mean_citation_a:.2%} · terminology {result.mean_terminology_a:.2%}")
    console.print(f"  B: citation {result.mean_citation_b:.2%} · terminology {result.mean_terminology_b:.2%}")


@app.command(name="tui-wizard")
def tui_wizard() -> None:
    """Launch the interactive recipe wizard (Textual TUI)."""
    from jw_finetune.tui.app import build_wizard_app

    build_wizard_app().run()


@app.command(name="tui-monitor")
def tui_monitor(
    workspace: Annotated[Path | None, typer.Option("--workspace", "-w")] = None,
) -> None:
    """Inline TUI monitor that tails events.jsonl in your terminal."""
    if workspace is None:
        base = Path("./jw-finetune-workspace")
        if not base.exists():
            raise typer.BadParameter("No --workspace provided and ./jw-finetune-workspace not found")
        workspace = _latest_run_dir(base)
    events_path = workspace / "events.jsonl"
    if not events_path.exists():
        events_path.write_text("", encoding="utf-8")
    from jw_finetune.tui.app import build_monitor_app

    build_monitor_app(events_path).run()


@app.command()
def monitor(
    workspace: Annotated[
        Path | None,
        typer.Option(
            "--workspace",
            "-w",
            help="Run directory; defaults to most recent run-* under ./jw-finetune-workspace.",
        ),
    ] = None,
    host: Annotated[str, typer.Option("--host")] = "127.0.0.1",
    port: Annotated[int, typer.Option("--port")] = 7860,
) -> None:
    """Start the live training dashboard at http://HOST:PORT."""
    if workspace is None:
        base = Path("./jw-finetune-workspace")
        if not base.exists():
            raise typer.BadParameter(f"No workspace specified and {base} not found; pass --workspace")
        workspace = _latest_run_dir(base)
    events_path = workspace / "events.jsonl"
    if not events_path.exists():
        events_path.write_text("", encoding="utf-8")  # create empty so tail can start
    console.print(f"[green]Dashboard:[/green] http://{host}:{port}")
    console.print(f"[dim]Tailing:   {events_path}[/dim]")
    from jw_finetune.monitor.app import run as run_monitor

    run_monitor(events_path, host=host, port=port)


@app.command()
def studio(
    workspace_root: Annotated[Path, typer.Option("--workspace-root", "-W")] = Path("./jw-finetune-workspace"),
    host: Annotated[str, typer.Option("--host")] = "127.0.0.1",
    port: Annotated[int, typer.Option("--port")] = 7860,
) -> None:
    """Start the full Web UI (monitor + studio: presets, runs, models, chat playground)."""
    workspace_root.mkdir(parents=True, exist_ok=True)
    # Pick latest run's events.jsonl as the live source; if no runs, use a workspace-level placeholder.
    runs = sorted(d for d in workspace_root.iterdir() if d.is_dir() and d.name.startswith("run-"))
    events_path = (runs[-1] / "events.jsonl") if runs else (workspace_root / "events.jsonl")
    if not events_path.exists():
        events_path.write_text("", encoding="utf-8")
    console.print(f"[green]Studio:[/green]  http://{host}:{port}/studio")
    console.print(f"[green]Monitor:[/green] http://{host}:{port}/")
    console.print(f"[dim]Tailing:  {events_path}[/dim]")
    from jw_finetune.monitor.studio import run_studio

    run_studio(events_path, workspace_root, host=host, port=port)


@app.command()
def run(
    recipe: Annotated[str | None, typer.Option("--recipe", "-r", help="Preset name.")] = None,
    recipe_file: Annotated[Path | None, typer.Option("--recipe-file")] = None,
    source: Annotated[
        list[Path] | None,
        typer.Option("--source", "-s", help="JWPUB/EPUB file or directory; may repeat."),
    ] = None,
    workspace: Annotated[Path, typer.Option("--workspace", "-w")] = Path("./jw-finetune-workspace"),
    export_fmt: Annotated[str, typer.Option("--export", help="Format to export at the end")] = "gguf",
    export_quant: Annotated[str, typer.Option("--export-quant", help="Quantization for export")] = "Q4_K_M",
) -> None:
    """End-to-end pipeline: prepare → train → export."""
    ctx = typer.get_current_context()
    ctx.invoke(
        prepare,
        recipe=recipe,
        recipe_file=recipe_file,
        source=source or [],
        workspace=workspace,
    )
    run_dir = _latest_run_dir(workspace)
    ctx.invoke(train, workspace=run_dir, resume=False)
    final_ckpt = run_dir / "checkpoints" / "final"
    ctx.invoke(
        export,
        checkpoint=final_ckpt,
        fmt=export_fmt,
        quant=export_quant,
        out=run_dir / "export",
    )


def main() -> None:  # pragma: no cover
    app()


if __name__ == "__main__":  # pragma: no cover
    sys.exit(app())
