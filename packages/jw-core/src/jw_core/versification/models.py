"""Pydantic models for the versification subpackage.

VerseCoord intentionally relaxes BibleRef: verse_start >= 0 to permit
superscriptions (BHS/LXX style: verse 0 = title). MappingResult embeds
(book, book_num, VerseCoord) instead of a full BibleRef so the verse_start=0
case can survive a round-trip through the model layer.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator

Tradition = Literal["nwt", "masoretic", "lxx", "vulgate"]

VersificationIssue = Literal[
    "superscription",
    "chapter_split",
    "verse_split",
    "verse_merge",
    "chapter_renumber",
    "verse_shift",
]


class VerseCoord(BaseModel):
    """A relaxed coordinate accepting verse 0 (superscription)."""

    chapter: int = Field(ge=0)
    verse_start: int = Field(ge=0)
    verse_end: int | None = Field(default=None, ge=0)


class VersificationMapping(BaseModel):
    """One catalog entry: how a single reference numbers across traditions."""

    book: str
    book_num: int = Field(ge=1, le=66)
    issue: VersificationIssue
    nwt: VerseCoord
    masoretic: VerseCoord | None = None
    lxx: VerseCoord | None = None
    vulgate: VerseCoord | None = None
    source: str = Field(min_length=1, description="Short academic citation.")
    explanation: dict[str, str] = Field(
        description="Original prose by maintainer, keyed 'en' | 'es' | 'pt'.",
    )

    @model_validator(mode="after")
    def _require_trilingual_explanation(self) -> VersificationMapping:
        required = {"en", "es", "pt"}
        present = {
            k
            for k, v in self.explanation.items()
            if isinstance(v, str) and v.strip()
        }
        missing = required - present
        if missing:
            raise ValueError(
                f"explanation missing languages: {sorted(missing)}"
            )
        return self

    def coord_for(self, tradition: Tradition) -> VerseCoord | None:
        """Return the catalog coordinate for one tradition, or None if absent."""
        return getattr(self, tradition)


class MappingResult(BaseModel):
    """Output of `to_canonical`."""

    ref_book: str
    ref_book_num: int = Field(ge=1, le=66)
    coord: VerseCoord
    from_tradition: Tradition
    to_tradition: Tradition
    is_discrepant: bool
    rationale: str | None = None
