"""SchedWeekType — authoritative weekly schedule (mid-week + weekend).

Excludes the display view-models (`MidweekMeetingDataType`,
`WeekendMeetingDataType`) from the TS source — those are formatted strings
derived from this state plus locale + sources, not authoritative data.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from jw_core.models_organized.week import Week

PublicTalkType = Literal["localSpeaker", "visitingSpeaker", "jwStreamRecording", "host", "group"]


class AssignmentCongregation(BaseModel):
    """A single name slot in the schedule, plus its CRDT timestamp."""

    model_config = ConfigDict(populate_by_name=True)

    type: str
    name: str
    value: str
    updatedAt: str
    solo: bool | None = None
    id: str | None = None
    deleted: bool | None = Field(default=None, alias="_deleted")


class WeekTypeCongregation(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    type: str
    value: Week
    updatedAt: str


class PublicTalkCongregation(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    type: str
    value: PublicTalkType
    updatedAt: str


class AssignmentAYFType(BaseModel):
    """Apply Yourself part with main_hall + 2 aux classes."""

    model_config = ConfigDict(populate_by_name=True)

    main_hall: AYFMainHall
    aux_class_1: AYFAuxClass
    aux_class_2: AYFAuxClass


class AYFMainHall(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    student: list[AssignmentCongregation]
    assistant: list[AssignmentCongregation]


class AYFAuxClass(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    student: AssignmentCongregation
    assistant: AssignmentCongregation


class OutgoingTalkCongregation(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    name: str
    number: str
    country: str
    address: str
    weekday: int
    time: str


class OutgoingTalkSchedule(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    deleted: bool = Field(alias="_deleted")
    updatedAt: str
    id: str
    synced: bool
    opening_song: str
    public_talk: int
    value: str
    type: str
    congregation: OutgoingTalkCongregation


class MidweekChairman(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    main_hall: list[AssignmentCongregation]
    aux_class_1: AssignmentCongregation


class MidweekTGWBibleReading(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    main_hall: list[AssignmentCongregation]
    aux_class_1: AssignmentCongregation
    aux_class_2: AssignmentCongregation


class MidweekLCCBS(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    conductor: list[AssignmentCongregation]
    reader: list[AssignmentCongregation]


class AuxFSG(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    value: str
    updatedAt: str


class MidweekMeeting(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    chairman: MidweekChairman
    opening_prayer: list[AssignmentCongregation]
    tgw_talk: list[AssignmentCongregation]
    tgw_gems: list[AssignmentCongregation]
    tgw_bible_reading: MidweekTGWBibleReading
    ayf_part1: AssignmentAYFType
    ayf_part2: AssignmentAYFType
    ayf_part3: AssignmentAYFType
    ayf_part4: AssignmentAYFType
    lc_part1: list[AssignmentCongregation]
    lc_part2: list[AssignmentCongregation]
    lc_part3: list[AssignmentCongregation]
    lc_cbs: MidweekLCCBS
    closing_prayer: list[AssignmentCongregation]
    circuit_overseer: AssignmentCongregation
    aux_fsg: AuxFSG | None = None
    week_type: list[WeekTypeCongregation]


class WeekendSpeaker(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    part_1: list[AssignmentCongregation]
    part_2: list[AssignmentCongregation]
    substitute: list[AssignmentCongregation]


class WeekendWTStudy(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    conductor: list[AssignmentCongregation]
    reader: list[AssignmentCongregation]


class WeekendMeeting(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    chairman: list[AssignmentCongregation]
    opening_prayer: list[AssignmentCongregation]
    public_talk_type: list[PublicTalkCongregation]
    speaker: WeekendSpeaker
    wt_study: WeekendWTStudy
    closing_prayer: list[AssignmentCongregation]
    circuit_overseer: AssignmentCongregation
    week_type: list[WeekTypeCongregation]
    outgoing_talks: list[OutgoingTalkSchedule]


class SchedWeekType(BaseModel):
    """One week of authoritative schedule state."""

    model_config = ConfigDict(populate_by_name=True)

    weekOf: str
    midweek_meeting: MidweekMeeting
    weekend_meeting: WeekendMeeting


# Forward-ref resolution for AssignmentAYFType (declared before its children).
AssignmentAYFType.model_rebuild()
