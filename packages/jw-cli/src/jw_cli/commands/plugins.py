"""`jw plugins` — list / verify / disable community plugins."""

from __future__ import annotations

import json
from pathlib import Path

import typer

from jw_core.plugins import get_plugins, verify_plugin
from jw_core.plugins.errors import PluginError
from jw_core.plugins.registry import GROUPS

app = typer.Typer(help="Manage community plugins (Fase 41).", no_args_is_help=True)

DEFAULT_CONFIG = Path.home() / ".jw-agent-toolkit" / "plugins.toml"


@app.command("list")
def list_plugins(
    json_out: bool = typer.Option(False, "--json", help="Emit JSON instead of a table."),
) -> None:
    """List all discovered plugins, grouped by extension point."""

    by_group: dict[str, list[dict[str, str]]] = {}
    for group in GROUPS:
        try:
            specs = get_plugins(group)
        except PluginError:
            specs = {}
        by_group[group] = [
            {
                "name": s.name,
                "dist": s.dist_name,
                "version": s.dist_version,
                "module": s.module,
                "attr": s.attr,
            }
            for s in specs.values()
        ]

    if json_out:
        typer.echo(json.dumps(by_group, indent=2, sort_keys=True))
        return

    for group, items in by_group.items():
        typer.echo(f"\n## {group}")
        if not items:
            typer.echo("  (no plugins)")
            continue
        for it in items:
            typer.echo(
                f"  {it['name']:30s}  {it['dist']:25s} v{it['version']}  {it['module']}:{it['attr']}"
            )


@app.command("verify")
def verify_plugin_cmd(
    name: str = typer.Argument(..., help="Plugin name (or dist:name for disambiguation)."),
    group: str = typer.Option(
        "jw_agent_toolkit.agents",
        "--group",
        help="Entry-point group to look the plugin up in.",
    ),
) -> None:
    """Run the contract + version check on a plugin and print the report."""

    try:
        rep = verify_plugin(name, group)
    except PluginError as exc:
        typer.echo(f"ERROR: {exc}", err=True)
        raise typer.Exit(code=2) from exc

    typer.echo(f"plugin: {rep.name}  ({rep.dist_name} v{rep.dist_version})")
    typer.echo(f"  group:              {rep.group}")
    typer.echo(f"  required present:   {list(rep.required_present)}")
    typer.echo(f"  required missing:   {list(rep.required_missing)}")
    typer.echo(f"  optional present:   {list(rep.optional_present)}")
    typer.echo(f"  optional missing:   {list(rep.optional_missing)}")
    typer.echo(f"  version constraint: {rep.version_constraint}")
    typer.echo(f"  version satisfied:  {rep.version_satisfied}")
    typer.echo(f"  status:             {'OK' if rep.ok else 'FAIL'}")

    if not rep.ok:
        raise typer.Exit(code=2)


@app.command("disable")
def disable(
    name: str = typer.Argument(..., help="Plugin name to deny-list persistently."),
    config: Path = typer.Option(
        DEFAULT_CONFIG, "--config", help="Path to persistent deny-list TOML."
    ),
) -> None:
    """Append a plugin name to the persistent deny list."""

    config = Path(config)
    config.parent.mkdir(parents=True, exist_ok=True)

    existing: list[str] = []
    if config.exists():
        for line in config.read_text().splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or stripped.startswith("[") or "=" in stripped:
                continue
            existing.append(stripped.strip('"').strip("'").rstrip(","))

    if name in existing:
        typer.echo(f"plugin {name!r} already in deny list at {config}")
        return

    existing.append(name)
    body = "[deny]\nplugins = [\n" + "".join(f'    "{n}",\n' for n in existing) + "]\n"
    config.write_text(body)
    typer.echo(f"plugin {name!r} added to {config}")
