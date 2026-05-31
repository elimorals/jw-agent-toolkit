"""Load GoldenCase YAML files from disk.

Convention: cases live in subdirs by layer (l1/, l2/, l3/) under one root.
One YAML file = one GoldenCase. Filenames are free-form but should be
descriptive (e.g. `apologetics_trinity_es.yaml`).
"""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import ValidationError

from jw_eval.models import GoldenCase, LayerName


def load_case_file(path: Path) -> GoldenCase:
    """Parse one YAML file into a GoldenCase. Raise ValueError on schema errors."""

    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"{path}: expected YAML mapping, got {type(raw).__name__}")
    try:
        return GoldenCase.model_validate(raw)
    except ValidationError as exc:
        raise ValueError(f"{path}: {exc}") from exc


def load_cases(root: Path, layers: list[LayerName] | None = None) -> list[GoldenCase]:
    """Recursively load every *.yaml under root, optionally filtering by layer."""

    cases: list[GoldenCase] = []
    if not root.exists():
        return cases
    for path in sorted(root.rglob("*.yaml")):
        case = load_case_file(path)
        if layers and case.layer not in layers:
            continue
        cases.append(case)
    return cases
