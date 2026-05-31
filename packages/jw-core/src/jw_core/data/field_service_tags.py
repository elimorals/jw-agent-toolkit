"""Controlled vocabulary for field-service hour entries.

Defaults cover the common modern forms of ministry. Users can override
locally by dropping a JSON file at
``~/.jw-agent-toolkit/field_service_tags_local.json``::

    {"add": ["hospital", "prison"], "remove": ["letter"]}

The override is **additive over the defaults** — `remove` drops items
out, `add` brings new ones in. Validation lives in the Pydantic models
in :mod:`jw_core.ministry.field_report` which read the resolved tag
set at import time of the model.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

DEFAULT_TAGS: tuple[str, ...] = (
    "street",
    "return_visit",
    "bible_study",
    "online",
    "phone",
    "cart",
    "letter",
    "other",
)


def _default_override_path() -> Path:
    raw = os.getenv(
        "JW_FIELD_TAGS_OVERRIDE",
        "~/.jw-agent-toolkit/field_service_tags_local.json",
    )
    return Path(raw).expanduser()


def load_tags(override_path: Path | None = None) -> tuple[str, ...]:
    """Return the effective tag tuple after applying any local override.

    Pass ``override_path=None`` to use the default user-config location.
    Pass an explicit ``Path`` (including non-existent) in tests to isolate.
    """

    path = override_path if override_path is not None else _default_override_path()
    tags = list(DEFAULT_TAGS)
    if not path.exists():
        return tuple(tags)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return tuple(tags)
    removed = set(data.get("remove") or [])
    added = [t for t in (data.get("add") or []) if t not in tags]
    tags = [t for t in tags if t not in removed] + added
    return tuple(tags)
