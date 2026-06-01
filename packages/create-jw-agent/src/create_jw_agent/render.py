"""Jinja2 + filesystem renderer.

Templates live under `create_jw_agent/templates/<type>/`. Files ending
in `.j2` are rendered; everything else is copied verbatim. Filenames may
contain `{{name}}` / `{{module}}` placeholders that are interpolated at
write time. Empty `.gitkeep` files preserve empty directories.
"""

from __future__ import annotations

import re
import shutil
from dataclasses import dataclass
from importlib.resources import as_file, files
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from create_jw_agent.validate import python_module_name


@dataclass(frozen=True)
class RenderContext:
    """Variables passed to every Jinja2 template + filename interpolation."""

    name: str          # kebab-case project name (e.g. "my-translator")
    module: str        # snake_case Python module name (e.g. "my_translator")
    type: str          # agent | parser | embedder | vlm | gen
    lang: str          # en | es | pt
    jw_core_version: str = ">=2.3,<3.0"
    license: str = "GPL-3.0"

    @classmethod
    def build(
        cls,
        *,
        name: str,
        type: str,
        lang: str = "en",
        jw_core_version: str = ">=2.3,<3.0",
        license: str = "GPL-3.0",
    ) -> "RenderContext":
        return cls(
            name=name,
            module=python_module_name(name),
            type=type,
            lang=lang,
            jw_core_version=jw_core_version,
            license=license,
        )


_PLACEHOLDER = re.compile(r"\{\{(\w+)\}\}")


def _interpolate_filename(name: str, ctx: RenderContext) -> str:
    mapping = {
        "name": ctx.name,
        "module": ctx.module,
        "type": ctx.type,
        "lang": ctx.lang,
    }
    return _PLACEHOLDER.sub(lambda m: mapping.get(m.group(1), m.group(0)), name)


class TargetExistsError(FileExistsError):
    """Raised when the output directory already exists."""


def render_template(
    *,
    template_type: str,
    output_dir: Path,
    ctx: RenderContext,
    overwrite: bool = False,
) -> list[Path]:
    """Render a template tree to disk. Returns list of created files.

    Raises TargetExistsError if output_dir exists and `overwrite=False`.
    """

    output_dir = Path(output_dir)
    if output_dir.exists() and not overwrite:
        raise TargetExistsError(str(output_dir))

    pkg = files("create_jw_agent.templates")
    template_root = pkg.joinpath(template_type)
    if not template_root.is_dir():
        raise FileNotFoundError(f"no template for type={template_type!r}")

    created: list[Path] = []
    with as_file(template_root) as src_root:
        env = Environment(
            loader=FileSystemLoader(str(src_root)),
            keep_trailing_newline=True,
            undefined=StrictUndefined,
        )
        for src in sorted(_walk(src_root)):
            rel = src.relative_to(src_root)
            rel_str = str(rel)
            if rel_str.endswith(".j2"):
                rel_str = rel_str[:-3]
            rel_str = _interpolate_filename(rel_str, ctx)
            target = output_dir / rel_str
            target.parent.mkdir(parents=True, exist_ok=True)
            if str(rel).endswith(".j2"):
                template = env.get_template(str(rel))
                rendered = template.render(**_ctx_to_dict(ctx))
                target.write_text(rendered, encoding="utf-8")
            elif src.name == ".gitkeep":
                # Keep the marker so empty dirs survive git.
                target.write_text("", encoding="utf-8")
            else:
                shutil.copy2(src, target)
            created.append(target)
    return created


def _walk(root: Path):
    for p in root.rglob("*"):
        if p.is_file():
            yield p


def _ctx_to_dict(ctx: RenderContext) -> dict[str, Any]:
    return {
        "name": ctx.name,
        "module": ctx.module,
        "type": ctx.type,
        "lang": ctx.lang,
        "jw_core_version": ctx.jw_core_version,
        "license": ctx.license,
    }
