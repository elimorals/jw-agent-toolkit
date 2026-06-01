"""Write-safe Obsidian wiki writer for jw-brain.

Extends jw_core.integrations.obsidian_vault patterns:
  - `.obsidian/` marker check
  - path-traversal defense via vault.resolve()
  - exclusive namespace under <vault>/<namespace>/
  - human_edited frontmatter flag honored
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path
from typing import Any

import yaml


class WriteOutsideNamespaceError(Exception):
    """Raised when a write would land outside <vault>/<namespace>/."""


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
        if target.exists():
            existing = target.read_text(encoding="utf-8")
            if "human_edited: true" in existing:
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
