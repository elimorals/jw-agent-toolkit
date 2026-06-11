"""``jw broadcasting visual-*`` - frame-level visual index CLI (Fase 69)."""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from jw_core.broadcasting.visual.engine import (
    index_video,
    search_index,
    stats_index,
)

broadcasting_visual_app = typer.Typer(
    help="Visual broadcasting frame-level index (Fase 69).",
    no_args_is_help=True,
)
console = Console()


@broadcasting_visual_app.command("index")
def cmd_index(
    video: str = typer.Argument(..., help="Local video path."),
    interval_s: float = typer.Option(
        5.0, "--interval", help="Seconds between sampled frames."
    ),
    root: str | None = typer.Option(
        None, "--root", help="Override index root directory."
    ),
    no_ffmpeg: bool = typer.Option(
        False, "--no-ffmpeg", help="Use fake sampler (testing)."
    ),
    video_id: str | None = typer.Option(
        None, "--video-id", help="Override the derived video_id (basename)."
    ),
) -> None:
    """Index a local video."""

    stats = index_video(
        video,
        root=Path(root) if root else None,
        interval_s=interval_s,
        use_real_ffmpeg=not no_ffmpeg,
        video_id=video_id,
    )
    console.print_json(stats.model_dump_json())


@broadcasting_visual_app.command("search")
def cmd_search(
    query: str = typer.Argument(...),
    top_k: int = typer.Option(10, "--top-k", "-k"),
    min_score: float = typer.Option(0.0, "--min-score"),
    root: str | None = typer.Option(None, "--root"),
) -> None:
    """Search the visual index."""

    hits = search_index(
        query,
        root=Path(root) if root else None,
        top_k=top_k,
        min_score=min_score,
    )
    if not hits:
        console.print("[dim]no hits[/]")
        return
    table = Table(title=f"visual_search({query!r}, top_k={top_k})")
    table.add_column("video_id")
    table.add_column("t")
    table.add_column("score")
    table.add_column("source")
    table.add_column("caption")
    for h in hits:
        table.add_row(
            h.video_id,
            f"{h.timestamp_s:.1f}s",
            f"{h.score:.3f}",
            h.source,
            h.caption[:80],
        )
    console.print(table)


@broadcasting_visual_app.command("stats")
def cmd_stats(
    root: str | None = typer.Option(None, "--root"),
) -> None:
    """Print storage stats for the visual index."""

    stats = stats_index(root=Path(root) if root else None)
    console.print_json(stats.model_dump_json())
