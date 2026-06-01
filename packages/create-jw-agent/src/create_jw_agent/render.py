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

from create_jw_agent.validate import python_module_name, validate_name


_UNSAFE_FILENAME_CHARS = frozenset(("/", "\\"))


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
        # Security: enforce the validate_name allowlist at construction time so
        # there is no path through which a malicious caller (CLI flag, library
        # use) gets to filename interpolation with a name that could contain
        # `/`, `\`, `..`, or other path-traversal payloads. validate_name
        # rejects everything outside `[a-z][a-z0-9-]*` kebab-case.
        err = validate_name(name)
        if err is not None:
            raise ValueError(f"invalid project name: {err.message}")
        return cls(
            name=name,
            module=python_module_name(name),
            type=type,
            lang=lang,
            jw_core_version=jw_core_version,
            license=license,
        )


_PLACEHOLDER = re.compile(r"\{\{(\w+)\}\}")


def _safe_replace_value(value: str) -> str:
    """Defense in depth: reject any substitution that contains path separators
    or '..'/.', even though `validate_name` already rules these out for
    `name`/`module`. This protects against future placeholders being added
    without remembering to validate."""

    if not isinstance(value, str):
        raise ValueError(f"non-string substitution value: {value!r}")
    if value in {"", ".", ".."}:
        raise ValueError(f"unsafe substitution value: {value!r}")
    if any(ch in value for ch in _UNSAFE_FILENAME_CHARS):
        raise ValueError(f"substitution value contains path separator: {value!r}")
    return value


def _interpolate_filename(name: str, ctx: RenderContext) -> str:
    mapping = {
        "name": _safe_replace_value(ctx.name),
        "module": _safe_replace_value(ctx.module),
        "type": _safe_replace_value(ctx.type),
        "lang": _safe_replace_value(ctx.lang),
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
    output_dir.mkdir(parents=True, exist_ok=True)
    out_root = output_dir.resolve()
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
            # Defense in depth: ensure the final resolved path stays inside
            # output_dir even if a template carries a `..` segment.
            target_resolved = (output_dir / rel_str).resolve()
            try:
                target_resolved.relative_to(out_root)
            except ValueError as exc:
                raise ValueError(
                    f"refusing to write outside output dir: {rel_str!r}"
                ) from exc
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
