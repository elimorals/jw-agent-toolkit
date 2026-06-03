"""PersonType — full congregant record (port of TS `person.ts`).

The TS shape uses `{value, updatedAt}` envelopes across every leaf field so
that CRDT-style sync can resolve conflicts per attribute. We mirror that
exactly using `Timestamped[T]`.
"""

from __future__ import annotations

from typing import Final, Literal

from pydantic import BaseModel, ConfigDict, Field

from jw_core.models_organized.assignment import AssignmentCode
from jw_core.models_organized.common import Timestamped

ALL_PRIVILEGE_TYPES: Final = ("elder", "ms")
PrivilegeType = Literal["elder", "ms"]

ALL_ENROLLMENT_TYPES: Final = ("AP", "FR", "FS", "FMF")
EnrollmentType = Literal["AP", "FR", "FS", "FMF"]


class AssignmentEntry(BaseModel):
    """An assignment configured for a person (`AssignmentType` in TS)."""

    model_config = ConfigDict(populate_by_name=True)

    type: str
    updatedAt: str
    values: list[AssignmentCode]


class TimeAwayEntry(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    deleted: bool = Field(alias="_deleted")
    updatedAt: str
    start_date: str
    end_date: str
    comments: str


class StatusHistoryEntry(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    deleted: bool = Field(alias="_deleted")
    updatedAt: str
    start_date: str
    end_date: str | None


class PrivilegeHistoryEntry(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    deleted: bool = Field(alias="_deleted")
    updatedAt: str
    privilege: PrivilegeType
    start_date: str
    end_date: str


class EnrollmentHistoryEntry(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    deleted: bool = Field(alias="_deleted")
    updatedAt: str
    enrollment: EnrollmentType
    start_date: str
    end_date: str


class EmergencyContactEntry(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    deleted: bool = Field(alias="_deleted")
    updatedAt: str
    name: str
    contact: str


class PublisherBaptizedSection(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    active: Timestamped[bool]
    anointed: Timestamped[bool]
    other_sheep: Timestamped[bool]
    baptism_date: Timestamped[str | None]
    history: list[StatusHistoryEntry]


class PublisherUnbaptizedSection(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    active: Timestamped[bool]
    history: list[StatusHistoryEntry]


class MidweekMeetingStudentSection(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    active: Timestamped[bool]
    history: list[StatusHistoryEntry]


class FamilyMembersSection(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    head: bool
    members: list[str]
    updatedAt: str


class PersonData(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    person_firstname: Timestamped[str]
    person_lastname: Timestamped[str]
    person_display_name: Timestamped[str]
    male: Timestamped[bool]
    female: Timestamped[bool]
    birth_date: Timestamped[str | None]
    assignments: list[AssignmentEntry]
    timeAway: list[TimeAwayEntry]
    archived: Timestamped[bool]
    disqualified: Timestamped[bool]
    email: Timestamped[str]
    address: Timestamped[str]
    phone: Timestamped[str]
    first_report: Timestamped[str | None] | None = None
    publisher_baptized: PublisherBaptizedSection
    publisher_unbaptized: PublisherUnbaptizedSection
    midweek_meeting_student: MidweekMeetingStudentSection
    privileges: list[PrivilegeHistoryEntry]
    enrollments: list[EnrollmentHistoryEntry]
    emergency_contacts: list[EmergencyContactEntry]
    categories: Timestamped[list[str]] | None = None
    family_members: FamilyMembersSection


class PersonType(BaseModel):
    """Top-level person record. `person_uid` is the stable id used for sync."""

    model_config = ConfigDict(populate_by_name=True)

    deleted: Timestamped[bool] = Field(alias="_deleted")
    person_uid: str
    person_data: PersonData
