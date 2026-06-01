"""Continuation/closure marker catalog.

Catalog lives in jw_core/data/continuation_markers.json so community
contributions (new languages) are JSON PRs with no Python change.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from functools import lru_cache
from importlib.resources import files


@dataclass(frozen=True)
class MarkerSet:
    continuation: tuple[str, ...]
    closure: tuple[str, ...]
    fingerprint: tuple[str, ...]


@lru_cache(maxsize=1)
def load_markers() -> dict[str, MarkerSet]:
    """Load the JSON catalog. Cached for the process lifetime."""

    data_pkg = files("jw_core.data")
    raw_path = data_pkg.joinpath("continuation_markers.json")
    raw = json.loads(raw_path.read_text(encoding="utf-8"))
    out: dict[str, MarkerSet] = {}
    for lang, payload in raw.items():
        if lang == "version":
            continue
        if not isinstance(payload, dict):
            continue
        out[lang] = MarkerSet(
            continuation=tuple(payload.get("continuation", [])),
            closure=tuple(payload.get("closure", [])),
            fingerprint=tuple(payload.get("fingerprint", [])),
        )
    return out


def is_continuation_start(paragraph: str, lang: str) -> bool:
    """True if `paragraph` starts with a continuation marker for `lang`."""

    catalog = load_markers()
    ms = catalog.get(lang)
    if ms is None:
        return False
    stripped = paragraph.lstrip()
    return any(_marker_matches_start(stripped, m) for m in ms.continuation)


def is_closure_start(paragraph: str, lang: str) -> bool:
    """True if `paragraph` opens with a closure marker for `lang`."""

    catalog = load_markers()
    ms = catalog.get(lang)
    if ms is None:
        return False
    stripped = paragraph.lstrip()
    return any(_marker_matches_start(stripped, m) for m in ms.closure)


def _marker_matches_start(text: str, marker: str) -> bool:
    if not text.startswith(marker):
        return False
    tail = text[len(marker):]
    if not tail:
        return True
    nxt = tail[0]
    return nxt in {",", ":", " ", "\t"}


def detect_language(text: str) -> str | None:
    """Cheap fingerprint-based detector. Returns None if score too low."""

    tokens = re.findall(r"\w+", text.lower())
    if not tokens:
        return None
    catalog = load_markers()
    scores: dict[str, int] = {}
    for lang, ms in catalog.items():
        fp = set(ms.fingerprint)
        scores[lang] = sum(1 for t in tokens if t in fp)
    if not scores:
        return None
    best_lang, best_score = max(scores.items(), key=lambda kv: kv[1])
    return best_lang if best_score >= 3 else None
