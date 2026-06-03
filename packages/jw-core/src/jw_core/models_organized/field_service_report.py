"""S-21 field service reports — daily + monthly (post-2023 layout).

The monthly form moved to "hours only if pioneer" — `field_service.daily`
and `field_service.monthly` are kept as strings (the TS source uses
strings everywhere to avoid float quirks; we follow suit).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict

TimerState = Literal["started", "not_started", "paused"]
ReportStatus = Literal["pending", "submitted", "confirmed"]


class TimerRecord(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    state: TimerState
    value: int
    start: int


class DailyBibleStudies(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    value: int
    records: list[str]


class DailyHours(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    field_service: str
    credit: str


class UserFieldServiceDailyReportData(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    deleted: bool
    updatedAt: str
    hours: DailyHours
    timer: TimerRecord
    bible_studies: DailyBibleStudies
    comments: str
    record_type: Literal["daily"]


class UserFieldServiceDailyReportType(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    report_date: str
    report_data: UserFieldServiceDailyReportData


class MonthlyHoursSplit(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    daily: str
    monthly: str


class MonthlyHours(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    field_service: MonthlyHoursSplit
    credit: MonthlyHoursSplit


class MonthlyBibleStudies(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    daily: int
    monthly: int
    records: list[str]


class UserFieldServiceMonthlyReportData(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    deleted: bool
    updatedAt: str
    shared_ministry: bool
    hours: MonthlyHours
    bible_studies: MonthlyBibleStudies
    comments: str
    record_type: Literal["monthly"]
    status: ReportStatus
    person_uid: str | None = None


class UserFieldServiceMonthlyReportType(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    report_date: str
    report_data: UserFieldServiceMonthlyReportData
