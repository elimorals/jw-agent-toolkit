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
    iso: str                # ISO-639-1 lowercase ("en", "es", "pt")
    jw_code: str            # JW internal code ("E", "S", "T")
    lp_tag: str             # wol.jw.org URL tag ("lp-e", "lp-s", "lp-t")
    display: str            # Human-readable name
    wol_resource: str       # `r1`/`r4`/etc. token used in wol URLs
    default_bible: str      # Default Bible publication code for this language


# Reference notes (verified 2026-05):
#   English   → /en/wol/b/r1/lp-e/nwtsty/...     (NWT Study Edition)
#   Spanish   → /es/wol/b/r4/lp-s/nwt/...        (Spanish NWT 2019)
#   Portuguese→ /pt/wol/b/r5/lp-t/nwt/...        (Portuguese NWT)
# These `r{N}` numbers are per-language resource versions. The Study Edition
# (`nwtsty`) is currently English-only; other languages use `nwt` or `Rbi8`.
_REGISTRY: dict[str, Language] = {
    "en": Language(iso="en", jw_code="E", lp_tag="lp-e", display="English",
                   wol_resource="r1", default_bible="nwtsty"),
    "es": Language(iso="es", jw_code="S", lp_tag="lp-s", display="Spanish",
                   wol_resource="r4", default_bible="nwt"),
    "pt": Language(iso="pt", jw_code="T", lp_tag="lp-t", display="Portuguese",
                   wol_resource="r5", default_bible="nwt"),
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
