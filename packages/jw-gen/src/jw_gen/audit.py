"""Audit log for jw-gen.

JSONL append-only file at $JW_GEN_HOME/audit.log (default ~/.jw-gen/audit.log).
One row per generation. Schema is fixed:

    {
      "audit_id":        "uuid4",
      "timestamp":       "ISO 8601 Z",
      "kind":            "image" | "audio" | "video",
      "provider":        "<name>",
      "prompt_sha256":   "<hex>",
      "output_path":     "<absolute path>",
      "watermark_mode":  "visible+metadata" | "metadata-only" | "off",
      "safety_flags":    {"logo_check": ..., "voice_clone_optin": ..., "realistic_faces_optin": ...},
      "warnings":        ["..."]
    }

The plaintext prompt is NEVER stored. The output content is NEVER stored.
"""

from __future__ import annotations

import gzip
import json
import os
import shutil
import uuid
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path


def _home() -> Path:
    raw = os.environ.get("JW_GEN_HOME")
    if raw:
        return Path(raw)
    return Path.home() / ".jw-gen"


def audit_log_path() -> Path:
    home = _home()
    home.mkdir(parents=True, exist_ok=True)
    return home / "audit.log"


def log_generation(
    *,
    kind: str,
    provider: str,
    prompt_sha256: str,
    output_path: Path,
    watermark_mode: str,
    safety_flags: dict[str, str],
    warnings: list[str],
    now: Callable[[], datetime] | None = None,
) -> dict[str, object]:
    ts_provider = now or (lambda: datetime.now(timezone.utc))
    ts = ts_provider().astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S") + "Z"
    event: dict[str, object] = {
        "audit_id": str(uuid.uuid4()),
        "timestamp": ts,
        "kind": kind,
        "provider": provider,
        "prompt_sha256": prompt_sha256,
        "output_path": str(output_path),
        "watermark_mode": watermark_mode,
        "safety_flags": safety_flags,
        "warnings": warnings,
    }
    path = audit_log_path()
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")
    return event


def rotate_log() -> Path | None:
    """Compress audit.log to audit.log.YYYY-MM.gz and start fresh.

    Returns the rotated path, or None if the log is empty / absent.
    """

    path = audit_log_path()
    if not path.exists() or path.stat().st_size == 0:
        return None
    stamp = datetime.now(timezone.utc).strftime("%Y-%m")
    dest = path.with_suffix(f".log.{stamp}.gz")
    with path.open("rb") as src, gzip.open(dest, "wb") as gz:
        shutil.copyfileobj(src, gz)
    path.write_text("", encoding="utf-8")
    return dest
