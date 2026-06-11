"""Pydantic models for the doctrinal-drift analyzer (Fase 72)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Era = Literal[
    "1900s",
    "1910s",
    "1920s",
    "1930s",
    "1940s",
    "1950s",
    "1960s",
    "1970s",
    "1980s",
    "1990s",
    "2000s",
    "2010s",
    "2020s",
]

ALL_ERAS: tuple[Era, ...] = (
    "1900s",
    "1910s",
    "1920s",
    "1930s",
    "1940s",
    "1950s",
    "1960s",
    "1970s",
    "1980s",
    "1990s",
    "2000s",
    "2010s",
    "2020s",
)


def year_to_era(year: int) -> Era | None:
    """Map a Gregorian year to its `Era` slot, or None if out of range."""

    if year < 1900 or year >= 2030:
        return None
    decade = (year // 10) * 10
    label = f"{decade}s"
    if label in ALL_ERAS:
        return label  # type: ignore[return-value]
    return None


Significance = Literal["minor", "moderate", "major"]
NLIVerdict = Literal["entails", "neutral", "contradicts", "skipped"]


class Citation(BaseModel):
    text: str
    wol_url: str | None = None
    pub_code: str
    year: int


class EraSnapshot(BaseModel):
    era: Era
    chunk_count: int = Field(ge=0)
    representative_chunks: list[str] = Field(default_factory=list)
    representative_citations: list[Citation] = Field(default_factory=list)
    cluster_count: int = Field(default=0, ge=0)
    cluster_center_embedding_id: int = Field(default=-1)


class DriftEvent(BaseModel):
    from_era: Era
    to_era: Era
    cosine_delta: float = Field(ge=0.0, le=2.0)
    significance: Significance
    summary_change: str
    from_citation: Citation
    to_citation: Citation
    nli_verdict: NLIVerdict = "skipped"


class DoctrinalDrift(BaseModel):
    query: str
    language: Literal["en", "es", "pt"]
    era_snapshots: list[EraSnapshot] = Field(default_factory=list)
    drift_events: list[DriftEvent] = Field(default_factory=list)
    summary_prose: str = ""
    explanatory_note: str
    insufficient_data: bool = False
    eras_skipped_low_data: list[Era] = Field(default_factory=list)
