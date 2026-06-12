"""Load Principle YAML files from disk.

Convention:
  - One YAML file may contain one principle (mapping at root) OR a list
    of principles under a top-level key `principles:`.
  - Filenames are free-form; conventionally `PF001-canon-only.yaml`.
  - Builtin principles ship under `principles/data/` and are loaded by
    `load_principles(None)`.

Matches the loader pattern already used by `jw_eval.loader.load_cases`:
ValidationError → ValueError with the path included, so CLI surfaces the
offending file.
"""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import ValidationError

from jw_eval.principles.models import Principle

BUILTIN_PRINCIPLES_DIR: Path = Path(__file__).parent / "data"


def _parse_one(raw: dict, path: Path) -> Principle:
    try:
        return Principle.model_validate(raw)
    except ValidationError as exc:
        raise ValueError(f"{path}: {exc}") from exc


def load_principles_file(path: Path) -> list[Principle]:
    """Parse one YAML file; supports single-principle or list form."""

    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if raw is None:
        return []
    if isinstance(raw, dict) and "principles" in raw:
        items = raw["principles"]
        if not isinstance(items, list):
            raise ValueError(f"{path}: top-level `principles:` must be a list, got {type(items).__name__}")
        return [_parse_one(item, path) for item in items]
    if isinstance(raw, list):
        return [_parse_one(item, path) for item in raw]
    if isinstance(raw, dict):
        return [_parse_one(raw, path)]
    raise ValueError(f"{path}: expected YAML mapping or list, got {type(raw).__name__}")


def load_principles(root: Path | None = None) -> list[Principle]:
    """Recursively load every *.yaml under root. None → builtin principles.

    Duplicates (same `id`) are de-duped keeping the LAST occurrence; this
    lets a user override a builtin by placing a same-id file in their own
    root. Principles are returned sorted by id for stable iteration.
    """

    target = root if root is not None else BUILTIN_PRINCIPLES_DIR
    by_id: dict[str, Principle] = {}
    if not target.exists():
        return []
    for path in sorted(target.rglob("*.yaml")):
        for p in load_principles_file(path):
            by_id[p.id] = p
    return sorted(by_id.values(), key=lambda p: p.id)
