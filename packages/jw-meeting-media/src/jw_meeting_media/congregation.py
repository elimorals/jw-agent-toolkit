"""F57.16 — Congregation registry for multi-congregation support.

Stores ``~/.jw-agent-toolkit/meetings/congregations.toml``::

    [congregations.norte]
    language = "es"
    weekend_kind = "weekend"
    midweek_kind = "midweek"
    notes = "Sala del Reino Norte"

    [congregations.sur]
    language = "en"
    notes = "Spanish-English bilingual"

Backwards compat: without registry, callers get the "default" congregation
matching pre-F57.16 behavior (single shared cache root).

This module owns ONLY the registry. Each command resolves a
``Congregation`` then composes its own per-congregation cache path under
``$JW_MEETING_HOME/<congregation_name>/...`` — keeping each congregation's
programs, downloads, and SQLite db isolated.
"""
from __future__ import annotations

import os
import tomllib
from dataclasses import asdict, dataclass
from pathlib import Path


def _default_registry_path() -> Path:
    base = Path(os.environ.get("JW_MEETING_HOME", "~/.jw-agent-toolkit/meetings"))
    return base.expanduser() / "congregations.toml"


@dataclass(frozen=True)
class Congregation:
    """A registered congregation profile.

    Attributes
    ----------
    name:
        Stable identifier used both in the TOML registry and as the
        per-congregation cache directory name. Should be filesystem-safe
        (no slashes/spaces recommended).
    language:
        ISO code (``"en"``, ``"es"``, ``"pt"``…) used as the default for
        ``jw meeting discover`` / ``download`` when ``--language`` is omitted.
    weekend_kind:
        Meeting kind label for weekend (currently always ``"weekend"`` — kept
        as a field for forward compat with custom labels).
    midweek_kind:
        Meeting kind label for midweek.
    notes:
        Free-form human-readable note (e.g. "Sala del Reino Norte").
    """

    name: str
    language: str = "en"
    weekend_kind: str = "weekend"
    midweek_kind: str = "midweek"
    notes: str = ""


# ── TOML emit (kept in-house to avoid pulling tomli-w as a runtime dep) ──


def _escape_toml_string(value: str) -> str:
    """Escape a string for a TOML basic-string literal.

    Implements the minimum of the spec needed for our registry: backslash
    and double-quote escaping plus control-char rejection. This is
    sufficient for ISO codes, congregation names, and notes.
    """
    out = value.replace("\\", "\\\\").replace('"', '\\"')
    out = out.replace("\n", "\\n").replace("\r", "\\r").replace("\t", "\\t")
    return out


def _emit_registry_toml(registry: dict[str, Congregation]) -> str:
    """Render the registry dict into a deterministic TOML string."""
    lines: list[str] = []
    for name in sorted(registry):
        cong = registry[name]
        lines.append(f"[congregations.{name}]")
        for key, value in asdict(cong).items():
            if key == "name":
                continue
            # Skip empty notes to keep the file tidy.
            if value == "" and key == "notes":
                continue
            if isinstance(value, str):
                lines.append(f'{key} = "{_escape_toml_string(value)}"')
            else:
                # Future-proof: serialise non-strings via repr — not used today.
                lines.append(f"{key} = {value!r}")
        lines.append("")  # blank line between tables
    return "\n".join(lines).rstrip("\n") + "\n" if lines else ""


# ── Public API ──────────────────────────────────────────────────────────


def load_registry(registry_path: Path | None = None) -> dict[str, Congregation]:
    """Return a name→Congregation dict. Empty if file missing."""
    path = Path(registry_path) if registry_path else _default_registry_path()
    if not path.exists():
        return {}
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    out: dict[str, Congregation] = {}
    for name, fields in (data.get("congregations") or {}).items():
        clean = {k: v for k, v in fields.items() if k != "name"}
        out[name] = Congregation(name=name, **clean)
    return out


def save_congregation(
    cong: Congregation, *, registry_path: Path | None = None
) -> None:
    """Add or update one congregation in the registry. Idempotent by name."""
    path = Path(registry_path) if registry_path else _default_registry_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    current = load_registry(path)
    current[cong.name] = cong
    path.write_text(_emit_registry_toml(current), encoding="utf-8")


def remove_congregation(
    name: str, *, registry_path: Path | None = None
) -> int:
    """Remove a congregation by name. Returns number of entries removed."""
    path = Path(registry_path) if registry_path else _default_registry_path()
    current = load_registry(path)
    if name not in current:
        return 0
    del current[name]
    path.write_text(_emit_registry_toml(current), encoding="utf-8")
    return 1


def resolve_congregation(
    *, name: str | None = None, registry_path: Path | None = None
) -> Congregation:
    """Resolve which congregation to use for a CLI/MCP command.

    Rules
    -----
    * ``name`` provided + exists → return that congregation.
    * ``name`` provided + missing → ``KeyError``.
    * ``name`` is ``None`` + 1 registered → return that one.
    * ``name`` is ``None`` + multiple registered → ``ValueError`` (the
      caller has to be explicit about which one to use).
    * ``name`` is ``None`` + registry empty/missing → ``Congregation("default")``
      for backwards compatibility with pre-F57.16 behavior.
    """
    registry = load_registry(registry_path)
    if name is not None:
        if name not in registry:
            raise KeyError(f"congregation not found: {name}")
        return registry[name]
    if not registry:
        return Congregation(name="default", language="en")
    if len(registry) == 1:
        return next(iter(registry.values()))
    raise ValueError(
        f"multiple congregations registered ({sorted(registry)}); "
        "specify --congregation NAME"
    )
