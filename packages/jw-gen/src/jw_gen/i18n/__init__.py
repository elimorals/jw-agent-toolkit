"""i18n catalogs for jw-gen.

All disclaimers, error messages, prompt suffixes, and logo-emulation keyword
blocklists live in three JSON files: en.json, es.json, pt.json. The keys
listed in REQUIRED_KEYS MUST exist in every catalog — `test_i18n.py`
enforces this.

This is a package (not a module) because the JSON catalogs live as siblings
of the loader. `Path(__file__).parent` resolves to this directory.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

Language = Literal["en", "es", "pt"]

REQUIRED_KEYS = (
    "watermark.default",
    "disclaimer.body",
    "disclaimer.realistic_people_warning",
    "safety.refuse.logo",
    "safety.refuse.voice_clone_no_consent",
    "safety.confirm.voice_clone",
    "safety.realism_suffix",
    "cli.cost_confirm",
)


@lru_cache(maxsize=8)
def _catalog(lang: Language) -> dict[str, Any]:
    path = Path(__file__).parent / f"{lang}.json"
    return json.loads(path.read_text(encoding="utf-8"))


def get_message(key: str, lang: Language = "es", **fmt: object) -> str:
    cat = _catalog(lang)
    if key not in cat:
        raise KeyError(f"i18n: missing key {key!r} in {lang}")
    value = cat[key]
    if isinstance(value, str) and fmt:
        return value.format(**fmt)
    return str(value)


def realism_suffix(lang: Language) -> str:
    return get_message("safety.realism_suffix", lang=lang)


def list_logo_keywords(lang: Language) -> list[str]:
    cat = _catalog(lang)
    raw = cat.get("logo_keywords", [])
    return [str(k).lower() for k in raw]


__all__ = [
    "Language",
    "REQUIRED_KEYS",
    "get_message",
    "list_logo_keywords",
    "realism_suffix",
]
