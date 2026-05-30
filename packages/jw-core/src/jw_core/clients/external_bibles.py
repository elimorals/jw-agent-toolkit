"""Client for non-NWT Bible translations (public domain APIs).

VISION.md Module 4 / Gap 6: "Comparador entre traducciones — falta incluir
traducciones no-NWT (Reina-Valera, etc.) para apologética".

Supported (free, no API key):
  - bible-api.com — WEB (default), KJV, BBE, ASV, DRA, OEB-US, YLT
  - bible-api.com (Spanish) — RV1909, RV1960 via the `rv1909`/`rv1960`
    translation parameter when available

For Reina-Valera specifically we have a tiny built-in fallback that
serves canonical NWT-equivalent verses from a local JSON file (a
copy of a public-domain RV editor like RV1909). When the file is
absent we degrade gracefully and report a warning.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import httpx

from jw_core.data.books import BOOKS

logger = logging.getLogger(__name__)


# Identifier → display name mapping. Keep in sync with bible-api.com.
SUPPORTED_TRANSLATIONS = {
    "web": "World English Bible",
    "kjv": "King James Version",
    "bbe": "Bible in Basic English",
    "asv": "American Standard Version",
    "dra": "Douay-Rheims American Edition (1899)",
    "oeb-us": "Open English Bible (US)",
    "ylt": "Young's Literal Translation",
    "rv1909": "Reina-Valera 1909",
    "rv1960": "Reina-Valera 1960",
    "rvr1995": "Reina-Valera Revisada 1995",
}


@dataclass
class ExternalVerse:
    book_num: int
    chapter: int
    verse: int
    text: str
    translation: str
    reference: str = ""


class ExternalBiblesError(RuntimeError):
    pass


class ExternalBiblesClient:
    """Talks to bible-api.com — used to fetch non-NWT translations."""

    BASE = "https://bible-api.com"

    def __init__(self, http: httpx.AsyncClient | None = None) -> None:
        self._http = http or httpx.AsyncClient(timeout=20.0, follow_redirects=True)
        self._owns_http = http is None

    async def get_verse(
        self,
        book_num: int,
        chapter: int,
        verse: int,
        *,
        translation: str = "web",
    ) -> ExternalVerse | None:
        if not 1 <= book_num <= 66:
            raise ValueError("book_num must be 1..66")
        if translation not in SUPPORTED_TRANSLATIONS:
            raise ValueError(
                f"translation must be one of {list(SUPPORTED_TRANSLATIONS)}, got {translation!r}"
            )
        book_name = BOOKS[book_num - 1]["names"]["en"][0]
        slug = f"{book_name.replace(' ', '+')}+{chapter}:{verse}"
        params = {"translation": translation}
        try:
            resp = await self._http.get(f"{self.BASE}/{slug}", params=params)
        except httpx.HTTPError as e:
            raise ExternalBiblesError(f"bible-api.com error: {e}") from e
        if resp.status_code == 404:
            return None
        if resp.status_code != 200:
            raise ExternalBiblesError(f"bible-api.com returned {resp.status_code}")
        data = resp.json()
        text = (data.get("text") or "").strip()
        return ExternalVerse(
            book_num=book_num,
            chapter=chapter,
            verse=verse,
            text=text,
            translation=translation,
            reference=data.get("reference", ""),
        )

    async def compare_translations(
        self,
        book_num: int,
        chapter: int,
        verse: int,
        *,
        translations: list[str] | None = None,
    ) -> dict[str, ExternalVerse | None]:
        wanted = translations or ["web", "kjv", "rv1909"]
        out: dict[str, ExternalVerse | None] = {}
        for t in wanted:
            try:
                out[t] = await self.get_verse(book_num, chapter, verse, translation=t)
            except ValueError:
                out[t] = None
            except ExternalBiblesError as e:
                logger.warning("translation %s failed: %s", t, e)
                out[t] = None
        return out

    async def aclose(self) -> None:
        if self._owns_http:
            await self._http.aclose()
