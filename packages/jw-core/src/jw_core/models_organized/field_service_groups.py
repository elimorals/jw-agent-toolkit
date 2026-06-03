"""FieldServiceGroupType — congregation field-service groups."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class FieldServiceGroupMember(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    person_uid: str
    sort_index: int
    isOverseer: bool
    isAssistant: bool


class FieldServiceGroupData(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    deleted: bool
    updatedAt: str
    name: str
    sort_index: int
    members: list[FieldServiceGroupMember]
    midweek_meeting: bool | None = None
    weekend_meeting: bool | None = None
    language_group: bool | None = None


class FieldServiceGroupType(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    group_id: str
    group_data: FieldServiceGroupData
