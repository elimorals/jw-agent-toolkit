"""Load Kingdom Songs metadata from bundled JSON, cache per language.

Loader uses `importlib.resources` so it works from a wheel install as well
as from a source checkout. There is no network and no filesystem write.

Each JSON file is a list of dicts with the schema declared in
docs/superpowers/specs/2026-05-30-fase-30-kingdom-songs-design.md.
"""

from __future__ import annotations

import json
import logging
from functools import lru_cache
from importlib import resources

from jw_core.languages import get_language
from jw_core.songs.models import KingdomSong, SongLookupError

logger = logging.getLogger(__name__)

# JW-internal codes used for the `wtlocale` query parameter.
_WTLOCALE_FOR_ISO = {"en": "E", "es": "S", "pt": "T"}


class SongRegistry:
    """Per-language Kingdom Songs registry, loaded from bundled JSON."""

    def __init__(self, language: str, songs: list[KingdomSong]) -> None:
        self._language = language
        self._by_number: dict[int, KingdomSong] = {s.number: s for s in songs}

    @classmethod
    def for_language(cls, language: str) -> SongRegistry:
        """Load the registry for one language from package data.

        Returns an empty registry (and emits a warning) when the requested
        language has no bundled JSON.
        """

        try:
            iso = get_language(language).iso
        except Exception:  # noqa: BLE001
            iso = language

        code = _WTLOCALE_FOR_ISO.get(iso)
        if code is None:
            logger.warning("kingdom-songs: no seed for language %r", language)
            return cls(language=iso, songs=[])

        package = "jw_core.data.kingdom_songs"
        filename = f"{code}.json"
        try:
            raw = resources.files(package).joinpath(filename).read_text(encoding="utf-8")
        except (FileNotFoundError, ModuleNotFoundError):
            logger.warning("kingdom-songs: missing data file %s", filename)
            return cls(language=iso, songs=[])

        records = json.loads(raw)
        songs: list[KingdomSong] = []
        for rec in records:
            payload = dict(rec)
            payload["language"] = iso
            if not payload.get("canonical_url"):
                payload["canonical_url"] = _derive_canonical_url(payload, code)
            payload.pop("doc_id", None)  # only used by the URL deriver
            songs.append(KingdomSong.model_validate(payload))
        return cls(language=iso, songs=songs)

    def lookup(self, number: int) -> KingdomSong:
        """Return the song or raise SongLookupError."""

        try:
            return self._by_number[number]
        except KeyError as exc:
            raise SongLookupError(
                f"song #{number} not in registry for language={self._language!r}"
            ) from exc

    def get(self, number: int) -> KingdomSong | None:
        return self._by_number.get(number)

    def all(self) -> list[KingdomSong]:
        return sorted(self._by_number.values(), key=lambda s: s.number)

    def language(self) -> str:
        return self._language


def _derive_canonical_url(rec: dict, wtlocale: str) -> str:
    """Stable jw.org URL for a song.

    Preference order (no network):
      1. If `rec["doc_id"]` is set → build a WOL discovery URL.
      2. Else → fall back to the public `finder?wtlocale=X&pub=sjj` page
         (always valid; lands on the songbook for that language).
    """

    doc_id = rec.get("doc_id")
    pub = rec.get("pub_symbol", "sjj")
    if doc_id:
        # We deliberately keep this minimal — the WOL URL pattern needs
        # `r1`/`lp-e` segments per language; that lives in `languages.get_language`
        # but we want this function to be cheap and offline-safe, so we use the
        # well-known public `finder` redirector which works for any pub+lang.
        return f"https://www.jw.org/finder?wtlocale={wtlocale}&pub={pub}&docid={doc_id}"
    return f"https://www.jw.org/finder?wtlocale={wtlocale}&pub={pub}"


@lru_cache(maxsize=8)
def get_registry(language: str = "en") -> SongRegistry:
    """Cached factory: return the registry for `language` (en/es/pt)."""

    return SongRegistry.for_language(language)
