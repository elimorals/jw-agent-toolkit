"""Load TOML catalog of counsel points and the applies-by-kind table."""

from __future__ import annotations

import tomllib
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import BaseModel

_HERE = Path(__file__).parent
_LANG_FILES = {
    "en": "catalog_en.toml",
    "es": "catalog_es.toml",
    "pt": "catalog_pt.toml",
}
_APPLIES_FILE = "applies_by_kind.toml"


class CounselPointDefinition(BaseModel):
    id: str
    title: str
    title_localized: str
    category: Literal["prosodic", "linguistic", "audience"]
    scorer: str
    short_description: str = ""


@lru_cache
def load_catalog(language: str) -> tuple[CounselPointDefinition, ...]:
    """Return the counsel points for a language (fallback to en)."""

    fname = _LANG_FILES.get(language) or _LANG_FILES["en"]
    with (_HERE / fname).open("rb") as f:
        data = tomllib.load(f)
    return tuple(
        CounselPointDefinition(**entry) for entry in data.get("points", [])
    )


@lru_cache
def _applies_by_kind() -> dict[str, frozenset[str]]:
    with (_HERE / _APPLIES_FILE).open("rb") as f:
        data = tomllib.load(f)
    return {
        kind: frozenset(spec["points"]) for kind, spec in data.items()
    }


def applies_to(part_kind: str) -> frozenset[str]:
    """Frozenset of point ids that apply to a given `part_kind`."""

    return _applies_by_kind().get(part_kind, frozenset())
