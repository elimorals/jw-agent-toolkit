"""Registry of study-book publications used by `study_conductor`.

Each entry is the minimum needed by the agent to load chapters from
JWPUB (local) or WOL (fallback) and render titles in the user's
language. New publications are added by appending entries; the agent
code never changes.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class StudyBook:
    pub_code: str
    title_by_lang: dict[str, str]
    languages: tuple[str, ...]
    total_chapters: int
    jwpub_symbol: str


CURRENT_STUDY_BOOK = "lff"

REGISTRY: dict[str, StudyBook] = {
    "lff": StudyBook(
        pub_code="lff",
        title_by_lang={
            "es": "Disfruta de la vida para siempre",
            "en": "Enjoy Life Forever!",
            "pt": "Desfrute a vida para sempre",
            "fr": "Profitez de la vie pour toujours",
            "de": "Genieße das Leben für immer",
            "it": "Goditi la vita per sempre",
            "ja": "永遠の命を楽しもう",
            "ko": "영원한 생명을 즐기십시오",
        },
        languages=("en", "es", "pt", "fr", "de", "it", "ja", "ko"),
        total_chapters=60,
        jwpub_symbol="lff",
    ),
}


def get_book(pub_code: str) -> StudyBook:
    try:
        return REGISTRY[pub_code]
    except KeyError as e:
        raise KeyError(f"Unknown study book pub_code={pub_code!r}") from e


def list_supported_languages() -> set[str]:
    langs: set[str] = set()
    for book in REGISTRY.values():
        langs.update(book.languages)
    return langs
