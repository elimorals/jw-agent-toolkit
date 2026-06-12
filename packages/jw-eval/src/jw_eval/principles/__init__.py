"""Versioned fidelity principles loaded from YAML.

A `Principle` encodes a fidelity rule that agents and the synth-judge can
consult before emitting output. Principles are NOT new doctrine — they
reflect rules that already exist in published material (lvs, od, etc.)
or in the codebase (jw_gen safety, apocrypha_detector). Codifying them
centrally lets every layer (judge, fidelity_wrap, regression suite) use
the same source of truth.

Public surface:
    load_principles(root) -> list[Principle]
    load_principles_file(path) -> list[Principle]
    Principle (pydantic model)
    Severity (Literal)
"""

from __future__ import annotations

from jw_eval.principles.loader import (
    BUILTIN_PRINCIPLES_DIR,
    load_principles,
    load_principles_file,
)
from jw_eval.principles.models import (
    DetectionRules,
    Principle,
    Severity,
    violations_for,
)

__all__ = [
    "BUILTIN_PRINCIPLES_DIR",
    "DetectionRules",
    "Principle",
    "Severity",
    "load_principles",
    "load_principles_file",
    "violations_for",
]
