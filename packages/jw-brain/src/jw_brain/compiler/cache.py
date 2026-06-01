"""Extraction cache by content_hash."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


def cache_key_for(*, content: str, prompt_version: str, provider_id: str) -> str:
    h = hashlib.sha256()
    h.update(content.encode("utf-8"))
    h.update(b"\x00")
    h.update(prompt_version.encode("utf-8"))
    h.update(b"\x00")
    h.update(provider_id.encode("utf-8"))
    return h.hexdigest()


class ExtractionCache:
    def __init__(self, cache_dir: Path) -> None:
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        return self.cache_dir / key[:2] / f"{key}.json"

    def get(self, key: str) -> dict[str, Any] | None:
        p = self._path(key)
        if not p.exists():
            return None
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            return None

    def put(self, key: str, value: dict[str, Any]) -> None:
        p = self._path(key)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
