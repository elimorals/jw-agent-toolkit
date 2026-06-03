"""MeetingAttendanceType — month-bucket of mid-week + weekend attendance."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from jw_core.models_organized.common import Timestamped


class AttendanceCongregation(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    present: int
    online: int
    type: str
    updatedAt: str


class WeeklyAttendance(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    midweek: list[AttendanceCongregation]
    weekend: list[AttendanceCongregation]


class MeetingAttendanceType(BaseModel):
    """Five weekly buckets so any month fits without dynamic keys."""

    model_config = ConfigDict(populate_by_name=True)

    deleted: Timestamped[bool] = Field(alias="_deleted")
    month_date: str
    week_1: WeeklyAttendance
    week_2: WeeklyAttendance
    week_3: WeeklyAttendance
    week_4: WeeklyAttendance
    week_5: WeeklyAttendance
