"""Metadata-only model for a Kingdom Song.

IMPORTANT: this model NEVER carries lyrics. The `theme` field is a single-
line paraphrase by the contributor — not a copy of the printed subtitle.
See docs/guias/canticos-del-reino.md for the rationale.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

from jw_core.parsers.reference import parse_reference

if TYPE_CHECKING:
    from jw_core.models import BibleRef


class SongLookupError(LookupError):
    """Raised when a Kingdom Song number is not in the registry."""


class KingdomSong(BaseModel):
    """One row in the Kingdom Songs registry. NO LYRICS."""

    number: int = Field(ge=1, le=200)
    title: str = Field(min_length=1, max_length=200)
    theme: str = Field(min_length=1, max_length=200)
    scriptures: list[str] = Field(default_factory=list)
    language: str
    pub_symbol: str = Field(default="sjj")
    canonical_url: str = Field(default="")

    def resolved_scriptures(self) -> list[BibleRef]:
        """Parse each `scriptures` entry via `parse_reference`.

        Unparseable entries are silently dropped.
        """

        refs: list[BibleRef] = []
        for raw in self.scriptures:
            ref = parse_reference(raw)
            if ref is not None:
                refs.append(ref)
        return refs
