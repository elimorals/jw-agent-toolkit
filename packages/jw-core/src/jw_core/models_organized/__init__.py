"""Schemas ported from `sws2apps/organized-app` (MIT) for interoperability.

The originals live as TypeScript types in `organized-app/src/definition/`.
These Pydantic v2 models preserve the same field shapes (including the CRDT
`{value, updatedAt}` pattern via `Timestamped[T]`) so a Python toolkit can
read/write the same JSON envelopes the React PWA produces.

Scope ported (Phase 50):
  - `common` — `Timestamped[T]`, the CRDT envelope
  - `assignment` — `AssignmentCode`, `AssignmentFieldType`
  - `person` — `PersonType`, privileges, enrollments, time-away history
  - `week` — `Week` enum, `WeekType`
  - `meeting_attendance` — `MeetingAttendanceType`
  - `field_service_groups` — `FieldServiceGroupType`
  - `field_service_report` — daily + monthly S-21 (post-2023 layout)
  - `schedule` — `SchedWeekType` (mid-week + weekend assignments)

Not ported (intentionally): MidweekMeetingDataType / WeekendMeetingDataType.
Those are display view-models specific to the React front end (formatted
strings, song titles by id), not authoritative state — a Python backend would
re-derive them from the schedule + sources.

License: see `README.md` (MIT credit to sws2apps/organized-app).
"""

from jw_core.models_organized.assignment import AssignmentCode, AssignmentFieldType
from jw_core.models_organized.common import Timestamped
from jw_core.models_organized.field_service_groups import FieldServiceGroupMember, FieldServiceGroupType
from jw_core.models_organized.field_service_report import (
    UserFieldServiceDailyReportType,
    UserFieldServiceMonthlyReportType,
)
from jw_core.models_organized.meeting_attendance import (
    AttendanceCongregation,
    MeetingAttendanceType,
    WeeklyAttendance,
)
from jw_core.models_organized.person import (
    ALL_ENROLLMENT_TYPES,
    ALL_PRIVILEGE_TYPES,
    EnrollmentType,
    PersonType,
    PrivilegeType,
)
from jw_core.models_organized.schedule import (
    AssignmentAYFType,
    AssignmentCongregation as AssignmentCongregationSched,
    PublicTalkType,
    SchedWeekType,
)
from jw_core.models_organized.week import Week, WeekType

__all__ = [
    "ALL_ENROLLMENT_TYPES",
    "ALL_PRIVILEGE_TYPES",
    "AssignmentAYFType",
    "AssignmentCode",
    "AssignmentCongregationSched",
    "AssignmentFieldType",
    "AttendanceCongregation",
    "EnrollmentType",
    "FieldServiceGroupMember",
    "FieldServiceGroupType",
    "MeetingAttendanceType",
    "PersonType",
    "PrivilegeType",
    "PublicTalkType",
    "SchedWeekType",
    "Timestamped",
    "UserFieldServiceDailyReportType",
    "UserFieldServiceMonthlyReportType",
    "Week",
    "WeekType",
    "WeeklyAttendance",
]
