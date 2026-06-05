"""Multi-tenant brain registry — persistent list of known brains.

Lives at ~/.jw-brain/registry.toml. Each brain is referenced by an alias
plus its absolute path. `init` auto-registers; `--brain <path>` and
`JW_BRAIN_HOME` continue to work without any alias lookup.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

DEFAULT_REGISTRY = Path.home() / ".jw-brain" / "registry.toml"


def registry_path() -> Path:
    return DEFAULT_REGISTRY


def load_registry(path: Path | None = None) -> dict[str, Path]:
    """Return alias → absolute Path map."""

    p = path or registry_path()
    if not p.exists():
        return {}
    try:
        raw = tomllib.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}
    brains = raw.get("brains") or {}
    out: dict[str, Path] = {}
    if isinstance(brains, dict):
        for alias, value in brains.items():
            if isinstance(value, str):
                out[alias] = Path(value).expanduser().resolve()
            elif isinstance(value, dict) and "path" in value:
                out[alias] = Path(value["path"]).expanduser().resolve()
    return out


def save_registry(brains: dict[str, Path], path: Path | None = None) -> Path:
    p = path or registry_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    lines = ["[brains]\n"]
    for alias, brain_path in sorted(brains.items()):
        lines.append(f'{alias} = "{brain_path}"\n')
    p.write_text("".join(lines), encoding="utf-8")
    return p


def register_brain(alias: str, brain_path: Path, *, registry: Path | None = None) -> None:
    brains = load_registry(registry)
    brains[alias] = Path(brain_path).expanduser().resolve()
    save_registry(brains, registry)


def resolve_alias(alias: str, *, registry: Path | None = None) -> Path | None:
    return load_registry(registry).get(alias)
