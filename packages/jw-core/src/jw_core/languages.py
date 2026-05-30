"""JW language code registry.

JW uses a single-letter (or two-letter) internal code per language. The website
uses ISO-639 lowercase codes in URL paths. Examples:

  English:    JW code "E", URL path "/en/", lp-tag "lp-e"
  Spanish:    JW code "S", URL path "/es/", lp-tag "lp-s"
  Portuguese: JW code "T", URL path "/pt/", lp-tag "lp-t"

Add more languages as needed.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Language:
    iso: str  # ISO-639-1 lowercase ("en", "es", "pt")
    jw_code: str  # JW internal code ("E", "S", "T")
    lp_tag: str  # wol.jw.org URL tag ("lp-e", "lp-s", "lp-t")
    display: str  # Human-readable name
    wol_resource: str  # `r1`/`r4`/etc. token used in wol URLs
    default_bible: str  # Default Bible publication code for this language


# Reference notes (verified 2026-05):
#   English   → /en/wol/b/r1/lp-e/nwtsty/...     (NWT Study Edition)
#   Spanish   → /es/wol/b/r4/lp-s/nwt/...        (Spanish NWT 2019)
#   Portuguese→ /pt/wol/b/r5/lp-t/nwt/...        (Portuguese NWT)
# These `r{N}` numbers are per-language resource versions. The Study Edition
# (`nwtsty`) is currently English-only; other languages use `nwt` or `Rbi8`.
_REGISTRY: dict[str, Language] = {
    "en": Language(iso="en", jw_code="E", lp_tag="lp-e", display="English", wol_resource="r1", default_bible="nwtsty"),
    "es": Language(iso="es", jw_code="S", lp_tag="lp-s", display="Spanish", wol_resource="r4", default_bible="nwt"),
    "pt": Language(iso="pt", jw_code="T", lp_tag="lp-t", display="Portuguese", wol_resource="r5", default_bible="nwt"),
    # Tier 1 expansion (Module 8 — Phase 16).
    "fr": Language(iso="fr", jw_code="F", lp_tag="lp-f", display="French", wol_resource="r30", default_bible="nwt"),
    "de": Language(iso="de", jw_code="X", lp_tag="lp-x", display="German", wol_resource="r10", default_bible="nwt"),
    "it": Language(iso="it", jw_code="I", lp_tag="lp-i", display="Italian", wol_resource="r6", default_bible="nwt"),
    "ru": Language(iso="ru", jw_code="U", lp_tag="lp-u", display="Russian", wol_resource="r8", default_bible="nwt"),
    "ja": Language(iso="ja", jw_code="J", lp_tag="lp-j", display="Japanese", wol_resource="r7", default_bible="nwt"),
    "ko": Language(iso="ko", jw_code="KO", lp_tag="lp-ko", display="Korean", wol_resource="r46", default_bible="nwt"),
    "zh": Language(iso="zh", jw_code="CHS", lp_tag="lp-chs", display="Chinese (Simplified)", wol_resource="r23", default_bible="nwt"),
}

# Sign-language registry (subset). VISION.md item: "Lenguas de señas (LSM/ASE)
# — JW Broadcasting tiene horas de contenido". These don't have a Bible
# `pub` code per se; they live under `vidcat:VIDEOONDEMAND` topic groups.
SIGN_LANGUAGES: dict[str, dict[str, str]] = {
    "ase": {
        "iso": "ase",
        "jw_code": "ASL",
        "display": "American Sign Language",
        "broadcasting_root": "https://www.jw.org/ase/biblioteca/videos/",
    },
    "lsm": {
        "iso": "lsm",
        "jw_code": "LSM",
        "display": "Lengua de Signos Mexicana",
        "broadcasting_root": "https://www.jw.org/lsm/biblioteca/videos/",
    },
    "lsc": {
        "iso": "lsc",
        "jw_code": "LSC",
        "display": "Lengua de Signos Colombiana",
        "broadcasting_root": "https://www.jw.org/lsc/biblioteca/videos/",
    },
    "bzs": {
        "iso": "bzs",
        "jw_code": "BVL",
        "display": "Brazilian Sign Language (Libras)",
        "broadcasting_root": "https://www.jw.org/bzs/biblioteca/videos/",
    },
}


def get_language(iso_or_jw: str) -> Language:
    """Resolve a language by ISO code ('es') or JW code ('S')."""
    key = iso_or_jw.lower()
    if key in _REGISTRY:
        return _REGISTRY[key]
    # Try JW code
    upper = iso_or_jw.upper()
    for lang in _REGISTRY.values():
        if lang.jw_code == upper:
            return lang
    raise KeyError(f"Unknown language: {iso_or_jw!r}")


def all_languages() -> list[Language]:
    return list(_REGISTRY.values())


# ── Phase 20: sign-language → spoken-base mapping ────────────────────


def get_book_language(jw_or_iso: str) -> str:
    """Return the spoken-base JW code to use for Bible book lookups.

    Sign languages (ASL, LSM, DGS, …) don't ship their own Bible-book
    name catalog — they reuse their spoken base. The plugin
    `signLanguage.ts` maintains this mapping; we mirror it here so the
    reference parser and the markdown utilities can resolve names
    correctly when the user is operating in a sign-language locale.

    Pass either a JW code ("LSM") or an ISO code ("mfs"). Returns the
    JW code of the spoken base ("S" for LSM), or the input unchanged
    when no mapping exists.
    """
    from jw_core.data.book_locales import (
        SIGN_LANGUAGE_BASE_MAP,
        ISO_TO_JW_CODE,
    )

    if not jw_or_iso:
        return jw_or_iso
    upper = jw_or_iso.upper()
    if upper in SIGN_LANGUAGE_BASE_MAP:
        return SIGN_LANGUAGE_BASE_MAP[upper]
    # Maybe it came in as an ISO sign-language code.
    iso = jw_or_iso.lower()
    candidate = ISO_TO_JW_CODE.get(iso)
    if candidate and candidate in SIGN_LANGUAGE_BASE_MAP:
        return SIGN_LANGUAGE_BASE_MAP[candidate]
    return upper if upper in SIGN_LANGUAGE_BASE_MAP else jw_or_iso
