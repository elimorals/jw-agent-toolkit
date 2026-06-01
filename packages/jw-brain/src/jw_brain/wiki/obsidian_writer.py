"""Write-safe Obsidian wiki writer for jw-brain.

Extends jw_core.integrations.obsidian_vault patterns:
  - `.obsidian/` marker check
  - path-traversal defense via vault.resolve()
  - exclusive namespace under <vault>/<namespace>/
  - human_edited frontmatter flag honored (fail-closed YAML parse)
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path
from typing import Any

import yaml


class WriteOutsideNamespaceError(Exception):
    """Raised when a write would land outside <vault>/<namespace>/."""


def _is_human_edited(path: Path) -> bool:
    """Parse YAML frontmatter strictly. Fail-closed: any parse error → treat as edited.

    This avoids the substring-bypass where an attacker-controlled body containing
    the literal string "human_edited: true" would lock the agent out.
    """

    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return True
    if not text.startswith("---"):
        return False
    # Frontmatter must close with "\n---" (a line consisting solely of "---").
    end = text.find("\n---", 3)
    if end == -1:
        return True  # malformed → fail closed
    try:
        fm = yaml.safe_load(text[3:end])
    except yaml.YAMLError:
        return True  # malformed → fail closed
    if not isinstance(fm, dict):
        return False
    return fm.get("human_edited") is True


class ObsidianWikiWriter:
    def __init__(self, *, vault_path: Path, namespace: str = "Second-Brain") -> None:
        self.vault_path = Path(vault_path).resolve()
        self.namespace = namespace
        self.root = self.vault_path / namespace
        if not (self.vault_path / ".obsidian").exists():
            raise ValueError(f"{vault_path} is not an Obsidian vault (no .obsidian/ marker)")
        self.root.mkdir(parents=True, exist_ok=True)

    def _safe_resolve(self, rel_path: str) -> Path:
        candidate = (self.root / rel_path).resolve()
        try:
            candidate.relative_to(self.root)
        except ValueError as exc:
            raise WriteOutsideNamespaceError(f"{candidate} is outside {self.root}") from exc
        return candidate

    def write_page(
        self,
        rel_path: str,
        *,
        body: str,
        frontmatter: dict[str, Any],
    ) -> Path:
        target = self._safe_resolve(rel_path)
        if target.exists() and _is_human_edited(target):
            return target
        target.parent.mkdir(parents=True, exist_ok=True)
        fm = {**frontmatter, "last_compiled_at": dt.datetime.now(dt.timezone.utc).isoformat()}
        rendered = f"---\n{yaml.safe_dump(fm, default_flow_style=False, sort_keys=False)}---\n\n{body}\n"
        target.write_text(rendered, encoding="utf-8")
        return target

    def append_log(self, operation: str, payload: dict[str, Any]) -> None:
        log_path = self.root / "log.md"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        ts = dt.datetime.now(dt.timezone.utc).isoformat()
        lines = [f"\n## {ts} — {operation}\n"]
        for k, v in payload.items():
            lines.append(f"- {k}: {v}\n")
        log_path.open("a", encoding="utf-8").write("".join(lines))
