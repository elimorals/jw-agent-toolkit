"""Pydantic models for weekly-meeting content (Fase 11).

Two meeting types per week:
  - Workbook (`mwb{YY}.{MM}`): "Vida y Ministerio Cristianos".
    Three sections: TREASURES, APPLY YOURSELF, LIVING AS CHRISTIANS.
    Each section has timed assignments (talk, demonstration, video, study).
  - Watchtower Study (`w{YY}.{MM}`): article + paragraph questions.

The shapes here are deliberately permissive — the JW layout has changed
multiple times across years and the parser falls back to plain text when a
piece of metadata isn't there.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

WORKBOOK_SECTIONS = ("treasures", "apply_yourself", "living_as_christians")


class WorkbookAssignment(BaseModel):
    """One scheduled item inside a workbook section."""

    title: str
    minutes: int | None = Field(default=None, description="Duration in minutes when announced")
    kind: str = Field(
        default="talk",
        description="'talk', 'demonstration', 'video', 'study', 'bible_reading', 'song'",
    )
    body: str = Field(
        default="",
        description="The descriptive paragraph that follows the bullet (excerpt from the workbook)",
    )
    references: list[str] = Field(
        default_factory=list,
        description="Bible refs or publication codes cited inline (raw text, may include URLs)",
    )
    cue: str = Field(
        default="",
        description="Suggested presentation cue when the workbook specifies one (e.g. 'th study 8')",
    )


class WorkbookSection(BaseModel):
    """One of the three top sections of a workbook week."""

    name: str = Field(description="'treasures', 'apply_yourself', or 'living_as_christians'")
    heading: str = Field(default="", description="Localized section heading as printed")
    assignments: list[WorkbookAssignment] = Field(default_factory=list)


class WorkbookWeek(BaseModel):
    """A single week of the meeting workbook."""

    week_of: str = Field(description="ISO date of the Monday opening the week (YYYY-MM-DD)")
    pub_code: str = Field(description="Workbook publication code, e.g. 'mwb24.07'")
    title: str = Field(default="", description="Headline as printed (often the weekly Bible reading)")
    bible_reading: str = Field(
        default="",
        description="The week's Bible reading passage (e.g. 'PROVERBS 1-3')",
    )
    song_opening: int | None = Field(default=None, description="Opening song number")
    song_middle: int | None = Field(default=None, description="Middle/transition song")
    song_closing: int | None = Field(default=None, description="Closing song")
    sections: list[WorkbookSection] = Field(default_factory=list)
    source_url: str = ""
    language: str = "en"

    @property
    def assignment_count(self) -> int:
        return sum(len(s.assignments) for s in self.sections)

    def section(self, name: str) -> WorkbookSection | None:
        for s in self.sections:
            if s.name == name:
                return s
        return None


class WatchtowerStudyParagraph(BaseModel):
    """One numbered paragraph inside a Watchtower Study article."""

    number: int
    text: str
    questions: list[str] = Field(default_factory=list, description="Study questions printed below the paragraph")
    scripture_refs: list[str] = Field(default_factory=list, description="Bible refs cited in the paragraph")


class WatchtowerStudy(BaseModel):
    """A Watchtower Study article ready for paragraph-level assignment."""

    pub_code: str = Field(description="Article publication code, e.g. 'w24.07'")
    study_number: int | None = Field(default=None, description="Study lesson index within the issue")
    title: str = ""
    theme_scripture: str = Field(default="", description="Theme verse printed under the title")
    summary: str = Field(default="", description="Lead paragraph or summary block")
    paragraphs: list[WatchtowerStudyParagraph] = Field(default_factory=list)
    source_url: str = ""
    language: str = "en"

    @property
    def paragraph_count(self) -> int:
        return len(self.paragraphs)


class CommentSuggestion(BaseModel):
    """A short comment script the user can deliver during a meeting."""

    paragraph_number: int | None = Field(default=None, description="Paragraph the comment ties to (None for opening)")
    duration_seconds: int = Field(
        default=20,
        description="Target duration; the brief comment etiquette is 15-30 s",
    )
    angle: str = Field(
        description="'main_point', 'practical_application', 'scripture_link', 'personal_experience'",
    )
    script: str = Field(description="The proposed comment (1-3 sentences)")
    scripture_refs: list[str] = Field(
        default_factory=list,
        description="Bible refs to mention; each has a verifiable wol.jw.org URL",
    )
    source_url: str = Field(
        default="",
        description="URL of the paragraph the comment is based on (always present)",
    )
