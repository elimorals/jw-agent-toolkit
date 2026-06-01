"""Typer CLI for create-jw-agent.

  uvx create-jw-agent my-translator --type=agent --lang=es

Network policy: the only network call is `--check-pypi`, which is opt-in
(default `False`) and uses lazy `httpx` import. Tests assert no network
happens without the flag.
"""

from __future__ import annotations

from pathlib import Path

import typer

from create_jw_agent import __version__
from create_jw_agent.i18n import detect_lang, translator
from create_jw_agent.render import RenderContext, TargetExistsError, render_template
from create_jw_agent.validate import validate_name

app = typer.Typer(help="Scaffolder for jw-agent-toolkit plugins (Fase 42).")


VALID_TYPES = ("agent", "parser", "embedder", "vlm", "gen")
VALID_LICENSES = ("GPL-3.0", "MIT", "Apache-2.0")


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"create-jw-agent {__version__}")
        raise typer.Exit()


@app.command()
def main(
    name: str = typer.Argument(..., help="Project name (kebab-case). No 'jw-' prefix."),
    type: str = typer.Option(
        "agent",
        "--type",
        help="Plugin type: " + " | ".join(VALID_TYPES),
        case_sensitive=False,
    ),
    lang: str | None = typer.Option(
        None,
        "--lang",
        help="UI language for CLI messages (en/es/pt). Auto-detect from $LANG if omitted.",
    ),
    output_dir: Path | None = typer.Option(
        None,
        "--output-dir",
        help="Output directory (defaults to ./NAME).",
    ),
    jw_core_version: str = typer.Option(
        ">=2.3,<3.0",
        "--jw-core-version",
        help="jw-core version range for the generated pyproject.toml.",
    ),
    license: str = typer.Option(
        "GPL-3.0",
        "--license",
        help="License for the generated project.",
        case_sensitive=False,
    ),
    check_pypi: bool = typer.Option(
        False,
        "--check-pypi/--no-check-pypi",
        help="Verify the name is not taken on PyPI (requires network).",
    ),
    quiet: bool = typer.Option(False, "--quiet", help="Suppress decorative output."),
    version: bool = typer.Option(
        False, "--version", callback=_version_callback, is_eager=True,
        help="Show version and exit.",
    ),
) -> None:
    """Create a new jw-agent-toolkit plugin from a template."""

    resolved_lang = (lang or detect_lang())
    t = translator(resolved_lang)

    # Validate name.
    err = validate_name(name)
    if err is not None:
        typer.echo(t("validate.invalid_name", reason=err.message), err=True)
        raise typer.Exit(code=2)

    # Validate type.
    plugin_type = type.lower()
    if plugin_type not in VALID_TYPES:
        typer.echo(
            f"--type must be one of {VALID_TYPES}, got {type!r}", err=True
        )
        raise typer.Exit(code=2)

    # Validate license.
    license_value = license
    for valid in VALID_LICENSES:
        if license.lower() == valid.lower():
            license_value = valid
            break
    else:  # noqa: PLW0120
        typer.echo(
            f"--license must be one of {VALID_LICENSES}, got {license!r}",
            err=True,
        )
        raise typer.Exit(code=2)

    # Optional PyPI name check (only call when explicitly requested).
    if check_pypi:
        if _pypi_name_taken(name):
            typer.echo(t("validate.pypi_taken", name=name), err=True)
            raise typer.Exit(code=2)

    # Render.
    target = output_dir or Path.cwd() / name
    ctx = RenderContext.build(
        name=name,
        type=plugin_type,
        lang=resolved_lang,
        jw_core_version=jw_core_version,
        license=license_value,
    )
    try:
        created = render_template(
            template_type=plugin_type, output_dir=target, ctx=ctx,
        )
    except TargetExistsError:
        typer.echo(t("render.target_exists", path=str(target)), err=True)
        raise typer.Exit(code=2) from None

    if not quiet:
        typer.echo(t("render.created", n=len(created), path=str(target)))
        typer.echo("")
        typer.echo(t("next_steps.header"))
        typer.echo(t("next_steps.line1", path=str(target)))
        typer.echo(t("next_steps.line2"))
        typer.echo(t("next_steps.line3"))
        typer.echo(t("next_steps.line4", module=ctx.module))
        typer.echo("")
        typer.echo(t("tagline"))


def _pypi_name_taken(name: str) -> bool:
    """Check if a name is registered on PyPI via JSON API. Lazy import."""

    try:
        import httpx
    except ImportError:
        typer.echo(
            "--check-pypi requires httpx. Install with: uv add 'create-jw-agent[pypi-check]'",
            err=True,
        )
        raise typer.Exit(code=2) from None

    url = f"https://pypi.org/pypi/{name}/json"
    try:
        resp = httpx.get(url, timeout=5.0)
    except Exception:  # noqa: BLE001
        return False
    return resp.status_code == 200
