"""Week-type enum + WeekType model (port of TS `week_type.ts`)."""

from __future__ import annotations

from enum import IntEnum
from typing import Any

from pydantic import BaseModel, ConfigDict


class Week(IntEnum):
    NORMAL = 1
    CO_VISIT = 2
    ASSEMBLY = 3
    CONVENTION = 4
    MEMORIAL = 5
    SPECIAL_TALK = 6
    TREASURES_PART = 7
    TREASURES_STUDENTS = 8
    STUDENTS_ASSIGNMENTS = 9
    STUDENTS_LIVING = 10
    LIVING_PART = 11
    PUBLIC_TALK = 12
    WATCHTOWER_STUDY = 13
    SPECIAL_TALK_ONLY = 14
    NO_MEETING = 20


class WeekType(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: Week
    sort_index: int
    language_group: bool
    # `meeting` references `MeetingType[]` in TS; we keep it loosely-typed
    # to avoid pulling the whole `app.ts` MeetingType graph (which is mostly
    # UI-routing concerns, not authoritative data).
    meeting: list[dict[str, Any]] | None = None
    week_type_name: dict[str, str]
