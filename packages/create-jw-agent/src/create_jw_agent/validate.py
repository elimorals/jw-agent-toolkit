"""Name validation per PEP 503 + reserved names.

We reject:
  - Names containing characters outside `[a-z0-9-]`.
  - Names starting with digit or hyphen.
  - Names ending with hyphen.
  - Consecutive hyphens.
  - PyPI-reserved or jw-agent-toolkit-internal names that would shadow core.

Naming convention enforced:
  - kebab-case (`my-translator`, NOT `my_translator` or `MyTranslator`)
  - lowercase only
  - No `jw-` prefix (reserves namespace for the core toolkit)
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_VALID_NAME = re.compile(r"^[a-z][a-z0-9]*(-[a-z0-9]+)*$")

RESERVED_NAMES = frozenset({
    # Reserves the jw- namespace for the toolkit itself.
    "jw-core",
    "jw-cli",
    "jw-mcp",
    "jw-rag",
    "jw-agents",
    "jw-finetune",
    "jw-eval",
    "jw-gen",
    "jw-brain",
    "jw-agent-toolkit",
    # Common conflicts.
    "create-jw-agent",
    "test",
    "tests",
    "src",
    "main",
})


@dataclass(frozen=True)
class ValidationError:
    code: str
    message: str


def validate_name(name: str) -> ValidationError | None:
    """Return None if the name is valid; otherwise a ValidationError."""

    if not name:
        return ValidationError("empty", "name cannot be empty")
    if name != name.lower():
        return ValidationError(
            "case",
            f"{name!r} must be lowercase kebab-case (e.g. 'my-translator')",
        )
    if name.startswith("jw-"):
        return ValidationError(
            "reserved-prefix",
            f"{name!r} starts with 'jw-' which is reserved for jw-agent-toolkit core packages",
        )
    if name in RESERVED_NAMES:
        return ValidationError(
            "reserved-name",
            f"{name!r} is a reserved name. Choose something distinctive.",
        )
    if not _VALID_NAME.match(name):
        return ValidationError(
            "invalid-shape",
            f"{name!r} must match kebab-case: [a-z][a-z0-9]*(-[a-z0-9]+)* "
            "(letters, digits, single hyphens; start with a letter).",
        )
    return None


def python_module_name(project_name: str) -> str:
    """Map kebab-case project name to snake_case Python module name."""

    return project_name.replace("-", "_")
