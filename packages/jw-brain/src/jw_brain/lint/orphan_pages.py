"""Detect wiki pages without graph edges."""

from __future__ import annotations

from pathlib import Path

import yaml


def find_orphan_pages(*, wiki_root: Path, backend) -> list[Path]:
    out: list[Path] = []
    for md in wiki_root.rglob("*.md"):
        if md.name in {"index.md", "log.md"}:
            continue
        text = md.read_text(encoding="utf-8")
        cid = _parse_frontmatter_canonical_id(text)
        if cid is None:
            continue
        neighbors = backend.neighbors(cid, hops=1)
        if not neighbors:
            out.append(md)
    return out


def _parse_frontmatter_canonical_id(text: str) -> str | None:
    if not text.startswith("---"):
        return None
    end = text.find("---", 3)
    if end == -1:
        return None
    try:
        fm = yaml.safe_load(text[3:end])
    except Exception:
        return None
    return fm.get("canonical_id") if isinstance(fm, dict) else None
