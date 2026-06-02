"""Lazy catalog registry.

Loads `data/versification_map.json` once per process and exposes the
catalog as a list of parsed VersificationMapping objects. No I/O at import.
"""

from __future__ import annotations

import json
from functools import lru_cache
from importlib import resources

from jw_core.versification.models import VersificationMapping


@lru_cache(maxsize=1)
def load_catalog() -> list[VersificationMapping]:
    """Return the parsed catalog. Cached for the life of the process."""

    raw = (
        resources.files("jw_core.data")
        .joinpath("versification_map.json")
        .read_text(encoding="utf-8")
    )
    payload = json.loads(raw)
    return [
        VersificationMapping.model_validate(entry)
        for entry in payload.get("discrepancies", [])
    ]


@lru_cache(maxsize=1)
def catalog_version() -> str:
    """Return the catalog version string from the JSON envelope."""

    raw = (
        resources.files("jw_core.data")
        .joinpath("versification_map.json")
        .read_text(encoding="utf-8")
    )
    return str(json.loads(raw).get("version", "0.0"))
