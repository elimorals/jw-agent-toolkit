"""Seed publication codes watched by PublicationsSource.

Hand-curated; audit annually. Each entry is (pub_code, is_periodical).
- Periodicals require an `issue=YYYYMM` to resolve a concrete file.
- Non-periodicals (books, brochures) resolve to the latest published edition.

Stable since 2026-05-30. Source: jw.org publication catalog.
"""

from __future__ import annotations

PERIODICALS: tuple[str, ...] = (
    "w",  # Watchtower (Study Edition)
    "wp",  # Watchtower (Public Edition)
    "g",  # Awake!
    "mwb",  # Meeting Workbook
)

NON_PERIODICALS: tuple[str, ...] = (
    "lff",  # Enjoy Life Forever! (current study book)
    "bhs",  # What Can the Bible Teach Us?
    "ll",  # Listen to God and Live Forever
    "lmd",  # Love People — Make Disciples
    "rj",  # Return to Jehovah
    "rk",  # The Kingdom Rules!
    "jy",  # Jesus — the Way, the Truth, the Life
    "ia",  # Imitate Their Faith
    "ed",  # Enjoy Life Forever brochure
    "fg",  # Good News
    "es",  # Yearbook (legacy; harmless if 404)
)

SEED_PUB_CODES: tuple[tuple[str, bool], ...] = tuple(
    [(code, True) for code in PERIODICALS] + [(code, False) for code in NON_PERIODICALS]
)
