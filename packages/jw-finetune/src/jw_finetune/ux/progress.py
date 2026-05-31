"""Rich-based progress bar helpers wired to the async synth orchestrator."""

from __future__ import annotations

from collections.abc import Callable
from contextlib import contextmanager


@contextmanager
def synth_progress_bar(total: int, *, label: str = "Synthesizing Q&A"):
    """Context manager that yields a `(task_id, advance_fn)` pair.

    Usage:
        with synth_progress_bar(len(chunks)) as (task_id, advance):
            await synthesize_chunks_async(
                chunks, progress=lambda done, total, pairs: advance(pairs),
                ...
            )

    Uses `rich.progress.Progress` with a custom layout that shows:
      * description
      * bar
      * % complete
      * elapsed / ETA
      * pairs counter (custom column)
    """
    from rich.progress import (
        BarColumn,
        MofNCompleteColumn,
        Progress,
        SpinnerColumn,
        TaskProgressColumn,
        TextColumn,
        TimeElapsedColumn,
        TimeRemainingColumn,
    )

    progress = Progress(
        SpinnerColumn(),
        TextColumn("[bold blue]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        MofNCompleteColumn(),
        TextColumn("· {task.fields[pairs]} pairs"),
        TimeElapsedColumn(),
        TextColumn("/"),
        TimeRemainingColumn(),
    )
    with progress:
        task_id = progress.add_task(label, total=total, pairs=0)

        def advance(pairs_total: int) -> None:
            progress.update(task_id, advance=1, pairs=pairs_total)

        yield task_id, advance


def make_progress_callback(advance: Callable[[int], None]):
    """Build a callback compatible with `synthesize_chunks_async(progress=)`."""

    def cb(done: int, total: int, pairs_so_far: int) -> None:
        advance(pairs_so_far)

    return cb
