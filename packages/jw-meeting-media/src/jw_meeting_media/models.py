"""Modelos del dominio reunión-en-vivo.

Diseñados clean-room desde la estructura semántica del WOL y desde los
schemas ya portados de organized-app (F51). NO derivados de M³.
"""

from __future__ import annotations

from datetime import date
from enum import Enum
from typing import Any

from jw_core.models import BibleRef
from pydantic import BaseModel, ConfigDict, Field, model_validator


class MeetingKind(str, Enum):
    """Tipo de reunión. Memorial y special_event NO son semanales."""

    MIDWEEK = "midweek"
    WEEKEND = "weekend"
    MEMORIAL = "memorial"
    SPECIAL_EVENT = "special_event"


class MediaKind(str, Enum):
    IMAGE = "image"
    VIDEO = "video"
    AUDIO = "audio"
    JWPUB = "jwpub"
    JWLPLAYLIST = "jwlplaylist"
    EXTERNAL_FILE = "external_file"  # user-added drag-drop


class MediaRef(BaseModel):
    """Referencia a una pieza de media — no descargada aún."""

    model_config = ConfigDict(frozen=False)

    kind: MediaKind
    title: str
    url: str = ""  # vacío si requiere resolución vía PubMediaClient
    pub_code: str | None = None
    track: int | None = None
    docid: int | None = None
    language: str | None = None
    duration_seconds: float | None = None
    sha256: str | None = None
    local_path: str | None = None  # se rellena tras descarga
    metadata: dict[str, Any] = Field(default_factory=dict)


class MeetingItem(BaseModel):
    """Una parte/punto del programa con sus refs."""

    model_config = ConfigDict(frozen=False)

    item_id: str
    title: str
    position: int = Field(ge=1, description="Orden dentro de la sección")
    duration_minutes: float | None = None
    bible_refs: list[BibleRef] = Field(default_factory=list)
    media_refs: list[MediaRef] = Field(default_factory=list)
    speaker_note: str = ""


class MeetingSection(BaseModel):
    """Bloque del programa (ej. 'Tesoros de la Palabra de Dios')."""

    model_config = ConfigDict(frozen=False)

    section_id: str
    title: str
    items: list[MeetingItem] = Field(default_factory=list)


class MeetingProgram(BaseModel):
    """Programa semanal completo descubierto desde WOL."""

    model_config = ConfigDict(frozen=False)

    language: str
    week_start: date
    kind: MeetingKind
    sections: list[MeetingSection] = Field(default_factory=list)
    source_url: str
    detected_at: str = ""  # ISO 8601 timestamp del scrape


class PresenterSession(BaseModel):
    """Estado de una sesión presenter en curso. Server-side."""

    model_config = ConfigDict(frozen=False)

    session_id: str
    program_url: str
    queue: list[MeetingItem] = Field(default_factory=list)
    cursor: int = 0
    playing: bool = False
    started_at: str = ""

    @model_validator(mode="after")
    def _validate_cursor(self) -> PresenterSession:
        if self.cursor < 0:
            raise ValueError("cursor must be >= 0")
        return self

    def advance(self) -> None:
        if self.cursor + 1 >= len(self.queue):
            raise IndexError("cursor out of range")
        self.cursor += 1

    def rewind(self) -> None:
        if self.cursor == 0:
            raise IndexError("already at start")
        self.cursor -= 1

    def current_item(self) -> MeetingItem | None:
        if not self.queue or self.cursor >= len(self.queue):
            return None
        return self.queue[self.cursor]
