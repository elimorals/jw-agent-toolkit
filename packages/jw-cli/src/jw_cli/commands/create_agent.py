"""`jw create-agent` — thin wrapper around the standalone create-jw-agent binary.

If the binary is on PATH (`pip install create-jw-agent` or `uvx`), we
delegate. Otherwise we hint at the install command.
"""

from __future__ import annotations

import shutil
import subprocess
import sys

import typer


def create_agent_cmd() -> None:
    """Scaffold a new jw-agent-toolkit plugin (delegates to create-jw-agent).

    All arguments and flags are passed through verbatim. Run
    `jw create-agent --help` to see what the standalone scaffolder supports.
    """

    binary = shutil.which("create-jw-agent")
    if binary is None:
        typer.echo(
            "create-jw-agent not found on PATH.\n"
            "Install with one of:\n"
            "  pipx install create-jw-agent\n"
            "  uvx create-jw-agent  (run without installing permanently)",
            err=True,
        )
        raise typer.Exit(code=1)

    # ctx.args contains everything after `jw create-agent` once typer's
    # context_settings allow extra args. We use sys.argv slicing for safety.
    try:
        idx = sys.argv.index("create-agent")
    except ValueError:
        forwarded: list[str] = []
    else:
        forwarded = sys.argv[idx + 1 :]

    result = subprocess.run([binary, *forwarded], check=False)
    raise typer.Exit(code=result.returncode)
