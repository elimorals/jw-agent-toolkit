"""Filler-word detector for es/en/pt with word-boundary matching."""

from __future__ import annotations

import re

_FILLERS: dict[str, list[str]] = {
    "en": ["um", "uh", "uhh", "like", "you know", "i mean", "so", "right"],
    "es": ["este", "esto", "o sea", "eh", "eeh", "pues", "bueno", "vale"],
    "pt": ["é", "tipo", "tipo assim", "então", "né", "pra você ver"],
}


def _word_class() -> str:
    """Word characters extended to cover accented Spanish/Portuguese letters."""
    return "A-Za-z0-9_ÀÁÂÃÄÅÆÇÈÉÊËÌÍÎÏÐÑÒÓÔÕÖØÙÚÛÜÝÞßàáâãäåæçèéêëìíîïðñòóôõöøùúûüýþÿ"


def _compile_pattern(words: list[str]) -> re.Pattern[str]:
    sorted_words = sorted(words, key=len, reverse=True)
    escaped = [re.escape(w) for w in sorted_words]
    wc = _word_class()
    return re.compile(
        rf"(?<![{wc}])(?:{'|'.join(escaped)})(?![{wc}])",
        re.IGNORECASE,
    )


_CACHE: dict[str, re.Pattern[str]] = {
    lang: _compile_pattern(words) for lang, words in _FILLERS.items()
}


def count_fillers(text: str, *, language: str = "es") -> int:
    """Return the count of filler words/phrases in `text` for `language`.

    Unknown languages fall back to English."""

    pattern = _CACHE.get(language) or _CACHE["en"]
    return len(pattern.findall(text or ""))
