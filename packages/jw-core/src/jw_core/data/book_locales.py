"""Bible book name catalog ported from `msakowski/obsidian-library-linker`.

The plugin ships per-locale YAML files with `id` (book number), `aliases`,
and three name lengths (`long`/`medium`/`short`). We converted them to
JSON at port time and load them lazily here so import-time stays cheap.

Schema of each `<JW_CODE>.json` file:

    [
        {
            "id": 1,
            "prefix": "1",          # optional — e.g. "1" in "1 Samuel"
            "aliases": ["genesis"],
            "name": { "long": "Genesis", "medium": "Gen.", "short": "Ge" }
        },
        …
    ]

Locales available (matching JW internal codes):

    English (E), Spanish (S), Portuguese (TPO), French (F), German (X),
    Italian (I), Russian (U), Japanese (J), Korean (KO), Czech (B),
    Croatian (C), Danish (D), Dutch (O), Finnish (FI), Tagalog (TG),
    Vietnamese (VT), Cibemba (CW).

Sign languages reuse their spoken base via `SIGN_LANGUAGE_BASE_MAP`
(ASL→E, LSM→S, DGS→X, etc.).
"""

from __future__ import annotations

import json
import logging
from functools import lru_cache
from pathlib import Path

logger = logging.getLogger(__name__)

__all__ = [
    "LocaleBook",
    "available_locales",
    "load_book_locale",
    "merge_into_books",
    "SIGN_LANGUAGE_BASE_MAP",
    "JW_CODE_TO_ISO",
    "ISO_TO_JW_CODE",
    "get_book_language_jw_code",
    "resolve_locale_chain",
]

_DATA_DIR = Path(__file__).parent / "bible_books"


# ── Sign-language base mapping (ported from signLanguage.ts) ──────────


SIGN_LANGUAGE_BASE_MAP: dict[str, str] = {
    "ASL": "E",
    "BSL": "E",
    "AUS": "E",
    "NZS": "E",
    "ISG": "E",
    "JML": "E",
    "DGS": "X",
    "OGS": "X",
    "FID": "FI",
    "LSM": "S",
    "LSE": "S",
    "LSA": "S",
    "BVL": "S",
    "SCH": "S",
    "LSC": "S",
    "SCR": "S",
    "CBS": "S",
    "SEC": "S",
    "LSG": "S",
    "SHO": "S",
    "LSN": "S",
    "PSL": "S",
    "LSP": "S",
    "SPE": "S",
    "LSS": "S",
    "LSU": "S",
    "LSV": "S",
    "NGT": "O",
    "KSL": "KO",
    "LGP": "TPO",
    "LSF": "F",
    "SBF": "F",
    "LSQ": "F",
    "LSI": "F",
    "BFL": "F",
    "CRS": "F",
    "CML": "F",
    "HZJ": "C",
    "SLV": "VT",
}


# ── JW code ↔ ISO code (sourced from plugin's languages.json) ────────


JW_CODE_TO_ISO: dict[str, str] = {
    "E": "en",
    "S": "es",
    "TPO": "pt-PT",
    "F": "fr",
    "X": "de",
    "I": "it",
    "U": "ru",
    "J": "ja",
    "KO": "ko",
    "B": "cs",
    "C": "hr",
    "D": "da",
    "O": "nl",
    "FI": "fi",
    "TG": "tl",
    "VT": "vi",
    "CW": "bem",
}

ISO_TO_JW_CODE: dict[str, str] = {v: k for k, v in JW_CODE_TO_ISO.items()}
# Also accept simpler ISO without region tag (pt → TPO).
ISO_TO_JW_CODE.setdefault("pt", "TPO")


def get_book_language_jw_code(jw_code: str) -> str:
    """Resolve sign-language JW codes to their spoken base for book lookups.

    Spoken codes pass through unchanged. Unknown codes return as-is so
    callers can still pass exotic codes and fail loudly downstream.
    """
    return SIGN_LANGUAGE_BASE_MAP.get(jw_code, jw_code)


def resolve_locale_chain(jw_or_iso: str) -> list[str]:
    """Return JSON files to try, in order, for a given language identifier.

    Pass an ISO ("es") or a JW code ("S") or a sign-language code ("LSM").
    Returns the canonical JW code(s) in fallback order. We try the
    sign-language code first (if present) so any caller that ships
    sign-language books later just works.
    """
    chain: list[str] = []
    if not jw_or_iso:
        return chain
    upper = jw_or_iso.upper()
    iso = jw_or_iso.lower()
    if upper in SIGN_LANGUAGE_BASE_MAP:
        chain.append(upper)
        chain.append(SIGN_LANGUAGE_BASE_MAP[upper])
    elif upper in JW_CODE_TO_ISO:
        chain.append(upper)
    elif iso in ISO_TO_JW_CODE:
        chain.append(ISO_TO_JW_CODE[iso])
    else:
        chain.append(upper)
    return chain


# ── Loader ───────────────────────────────────────────────────────────


class LocaleBook(dict):
    """Typed view over one book entry. Dict-shaped for cheap JSON parity."""

    @property
    def book_num(self) -> int:
        return int(self["id"])

    @property
    def prefix(self) -> str:
        return self.get("prefix", "") or ""

    @property
    def aliases(self) -> list[str]:
        return list(self.get("aliases", []) or [])

    @property
    def name_long(self) -> str:
        return self.get("name", {}).get("long", "")

    @property
    def name_medium(self) -> str:
        return self.get("name", {}).get("medium", "")

    @property
    def name_short(self) -> str:
        return self.get("name", {}).get("short", "")

    def all_names(self) -> list[str]:
        """Every name variant + aliases, deduped (case-preserving for the first)."""
        seen: set[str] = set()
        out: list[str] = []
        for raw in (
            self.name_long,
            self.name_medium,
            self.name_medium.rstrip("."),
            self.name_short,
            self.name_short.rstrip("."),
            *self.aliases,
        ):
            v = (raw or "").strip()
            if not v:
                continue
            key = v.lower()
            if key in seen:
                continue
            seen.add(key)
            out.append(v)
        # With explicit chapter prefix (e.g. "1 Samuel" → prepend "1 ").
        if self.prefix:
            prefixed = [f"{self.prefix} {n}" for n in list(out)]
            for p in prefixed:
                key = p.lower()
                if key not in seen:
                    seen.add(key)
                    out.append(p)
        return out


@lru_cache(maxsize=64)
def load_book_locale(jw_code: str) -> list[LocaleBook]:
    """Load `<JW_CODE>.json` from data/bible_books/. Returns [] when missing."""
    if not jw_code:
        return []
    path = _DATA_DIR / f"{jw_code}.json"
    if not path.exists():
        logger.debug("No book locale file for %r at %s", jw_code, path)
        return []
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        logger.warning("Failed to load book locale %r: %s", jw_code, e)
        return []
    return [LocaleBook(b) for b in raw if isinstance(b, dict) and "id" in b]


def available_locales() -> list[str]:
    """Sorted list of JW codes that have a JSON file shipped."""
    return sorted(p.stem for p in _DATA_DIR.glob("*.json"))


# ── BOOKS merger ──────────────────────────────────────────────────────


# Locale codes whose names take precedence in cross-language collisions.
# When a short alias like "Ap" exists in two languages pointing at different
# books, we keep the alias only for the book of higher-priority locales.
# Order = priority (most authoritative first).
_PRIORITY_LOCALES: tuple[str, ...] = ("E", "S", "TPO", "F", "X", "I", "U", "J", "KO")


def _alias_key(name: str) -> str:
    """Mirror `jw_core.parsers.reference._norm_key` for collision detection.

    Imported lazily here to avoid a circular dependency between the data
    layer and the parser (parser imports BOOKS).
    """
    import re
    import unicodedata

    normalized = "".join(c for c in unicodedata.normalize("NFD", name.lower()) if not unicodedata.combining(c))
    return re.sub(r"[\s.\-]+", "", normalized)


def merge_into_books(base_books: list[dict]) -> list[dict]:
    """Enrich `BOOKS` with name aliases from every available locale.

    For each book id 1..66 we append the loaded locale's `all_names()`
    under the corresponding ISO code, preserving existing entries the
    `base_books` list already had. Order: existing first (preferred for
    display), then merged. Deduped case-insensitively.

    Cross-language collision handling: when a short alias (e.g. "Ap")
    points at different books across locales, we keep it only for the
    book it already maps to in a higher-priority locale (en / es / pt
    / fr / de / it / ru / ja / ko). Lower-priority locales drop the
    conflicting alias for that book so the parser stays unambiguous.

    The base list MUST already contain one entry per book (1..66) — we
    enrich, we don't seed.
    """
    by_num = {b["num"]: b for b in base_books}

    # First pass: build a global alias map from existing names + every locale,
    # in priority order. Locales not in `_PRIORITY_LOCALES` come last.
    # Keys use the same normalization the reference parser applies so
    # accented variants ("Áp" → "ap") collide as they will at lookup time.
    alias_owner: dict[str, int] = {}

    # Seed from base_books (which already covers en/es/pt + tier-1).
    for b in base_books:
        for names in b.get("names", {}).values():
            for name in names:
                alias_owner.setdefault(_alias_key(name), b["num"])

    locales_ordered = list(_PRIORITY_LOCALES) + [c for c in available_locales() if c not in _PRIORITY_LOCALES]
    seen_locales: set[str] = set()
    for jw_code in locales_ordered:
        if jw_code in seen_locales:
            continue
        seen_locales.add(jw_code)
        iso = JW_CODE_TO_ISO.get(jw_code)
        if not iso:
            continue
        for lb in load_book_locale(jw_code):
            book = by_num.get(lb.book_num)
            if book is None:
                continue
            names_for_iso = list(book.setdefault("names", {}).get(iso, []))
            for name in lb.all_names():
                key = _alias_key(name)
                if not key:
                    continue
                # If this alias already belongs to a different book, skip.
                existing_owner = alias_owner.get(key)
                if existing_owner is not None and existing_owner != lb.book_num:
                    continue
                if not any(_alias_key(n) == key for n in names_for_iso):
                    names_for_iso.append(name)
                alias_owner.setdefault(key, lb.book_num)
            book["names"][iso] = names_for_iso
    return base_books
