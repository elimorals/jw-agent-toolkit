"""i18n loader for create-jw-agent CLI messages.

Auto-detect from $LANG / $LC_ALL; override with --lang. Fallback to en if
the requested language is missing or the key is missing.
"""

from __future__ import annotations

import json
import os
from functools import lru_cache
from importlib.resources import files
from typing import Any


SUPPORTED = ("en", "es", "pt")
DEFAULT_LANG = "en"


def detect_lang() -> str:
    """Detect from environment. LANG=es_ES.UTF-8 → 'es'. Fallback 'en'."""

    for var in ("LC_ALL", "LANG"):
        value = os.environ.get(var, "").strip()
        if not value:
            continue
        # Extract first 2 chars before separators _, ., -
        code = value.split(".")[0].split("_")[0].split("-")[0].lower()
        if code in SUPPORTED:
            return code
    return DEFAULT_LANG


@lru_cache(maxsize=8)
def _load(lang: str) -> dict[str, str]:
    if lang not in SUPPORTED:
        lang = DEFAULT_LANG
    pkg = files("create_jw_agent.lang")
    raw = pkg.joinpath(f"{lang}.json").read_text(encoding="utf-8")
    return json.loads(raw)


def translator(lang: str | None = None) -> "Translator":
    """Build a callable translator. None → auto-detect."""

    resolved = lang or detect_lang()
    return Translator(resolved)


class Translator:
    def __init__(self, lang: str) -> None:
        self.lang = lang if lang in SUPPORTED else DEFAULT_LANG
        self._strings = _load(self.lang)
        self._fallback = _load(DEFAULT_LANG) if self.lang != DEFAULT_LANG else self._strings

    def __call__(self, key: str, **kwargs: Any) -> str:
        template = self._strings.get(key) or self._fallback.get(key) or key
        try:
            return template.format(**kwargs)
        except (KeyError, IndexError):
            return template
