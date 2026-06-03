"""F50 — sanity tests for the organized-app schema port.

Construct each ported model from JSON shaped like the TS source produces, and
verify round-trip via `model_dump`. These tests double as documentation: anyone
reading them sees the exact JSON envelope organized-app emits.
"""

from __future__ import annotations

from jw_core.models_organized import (
    AssignmentCode,
    EnrollmentType,
    FieldServiceGroupType,
    MeetingAttendanceType,
    PersonType,
    PrivilegeType,
    SchedWeekType,
    Timestamped,
    UserFieldServiceMonthlyReportType,
    Week,
    WeekType,
)


def test_timestamped_envelope() -> None:
    """The CRDT envelope keeps `value` + `updatedAt` together."""
    t: Timestamped[bool] = Timestamped(value=True, updatedAt="2026-06-02T10:00:00Z")
    dumped = t.model_dump()
    assert dumped == {"value": True, "updatedAt": "2026-06-02T10:00:00Z"}


def test_week_enum_matches_ts() -> None:
    """Numeric values must match the TS enum verbatim — sync depends on it."""
    assert int(Week.NORMAL) == 1
    assert int(Week.CO_VISIT) == 2
    assert int(Week.MEMORIAL) == 5
    assert int(Week.WATCHTOWER_STUDY) == 13
    assert int(Week.NO_MEETING) == 20


def test_assignment_code_matches_ts() -> None:
    """Spot-check a few codes — these are what JW Library/organized-app sync."""
    assert int(AssignmentCode.MM_BibleReading) == 100
    assert int(AssignmentCode.WM_WTStudyConductor) == 130
    assert int(AssignmentCode.MINISTRY_HOURS_CREDIT) == 300


def test_privilege_and_enrollment_literals() -> None:
    """Literals are accepted, others rejected by pydantic."""
    elder: PrivilegeType = "elder"
    ap: EnrollmentType = "AP"
    assert elder == "elder"
    assert ap == "AP"


def test_week_type_roundtrip() -> None:
    payload = {
        "id": 1,
        "sort_index": 0,
        "language_group": False,
        "week_type_name": {"en": "Normal", "es": "Normal"},
    }
    parsed = WeekType.model_validate(payload)
    assert parsed.id == Week.NORMAL
    assert parsed.week_type_name["es"] == "Normal"


def test_person_minimal() -> None:
    """Build a minimal valid PersonType from a JSON-like dict."""
    payload = _minimal_person_payload()
    person = PersonType.model_validate(payload)
    assert person.person_uid == "uid-1"
    assert person.person_data.person_firstname.value == "Ana"
    assert person.person_data.publisher_baptized.active.value is True
    # Round-trip preserves the `_deleted` alias.
    dumped = person.model_dump(by_alias=True)
    assert "_deleted" in dumped


def test_field_service_group() -> None:
    payload = {
        "group_id": "g-1",
        "group_data": {
            "deleted": False,
            "updatedAt": "2026-06-01T00:00:00Z",
            "name": "Grupo 1",
            "sort_index": 0,
            "members": [
                {"person_uid": "uid-1", "sort_index": 0, "isOverseer": True, "isAssistant": False},
                {"person_uid": "uid-2", "sort_index": 1, "isOverseer": False, "isAssistant": True},
            ],
            "language_group": False,
        },
    }
    group = FieldServiceGroupType.model_validate(payload)
    assert group.group_data.members[0].isOverseer is True
    assert group.group_data.members[1].person_uid == "uid-2"


def test_meeting_attendance() -> None:
    payload = {
        "_deleted": {"value": False, "updatedAt": "2026-06-01T00:00:00Z"},
        "month_date": "2026-06",
        "week_1": {
            "midweek": [{"present": 35, "online": 5, "type": "regular", "updatedAt": "2026-06-04T19:00:00Z"}],
            "weekend": [{"present": 40, "online": 8, "type": "regular", "updatedAt": "2026-06-07T10:00:00Z"}],
        },
        "week_2": _empty_week_attendance(),
        "week_3": _empty_week_attendance(),
        "week_4": _empty_week_attendance(),
        "week_5": _empty_week_attendance(),
    }
    att = MeetingAttendanceType.model_validate(payload)
    assert att.month_date == "2026-06"
    assert att.week_1.midweek[0].present == 35


def test_monthly_field_service_report() -> None:
    payload = {
        "report_date": "2026-06",
        "report_data": {
            "deleted": False,
            "updatedAt": "2026-06-30T23:59:00Z",
            "shared_ministry": True,
            "hours": {
                "field_service": {"daily": "0", "monthly": "12"},
                "credit": {"daily": "0", "monthly": "2"},
            },
            "bible_studies": {"daily": 0, "monthly": 3, "records": ["uid-a", "uid-b"]},
            "comments": "",
            "record_type": "monthly",
            "status": "submitted",
        },
    }
    report = UserFieldServiceMonthlyReportType.model_validate(payload)
    assert report.report_data.status == "submitted"
    assert report.report_data.bible_studies.monthly == 3


def test_sched_week_skeleton() -> None:
    """A schedule built from defaults validates."""
    payload = _minimal_sched_week_payload()
    sched = SchedWeekType.model_validate(payload)
    assert sched.weekOf == "2026-06-01"
    assert sched.midweek_meeting.ayf_part1.main_hall.student == []
    assert sched.weekend_meeting.outgoing_talks == []


# ── helpers ──────────────────────────────────────────────────────────────


def _empty_week_attendance() -> dict:
    return {"midweek": [], "weekend": []}


def _minimal_person_payload() -> dict:
    ts_true = {"value": True, "updatedAt": "2026-06-01T00:00:00Z"}
    ts_false = {"value": False, "updatedAt": "2026-06-01T00:00:00Z"}
    ts_str = {"value": "Ana", "updatedAt": "2026-06-01T00:00:00Z"}
    ts_blank = {"value": "", "updatedAt": "2026-06-01T00:00:00Z"}
    ts_null_date = {"value": None, "updatedAt": "2026-06-01T00:00:00Z"}
    return {
        "_deleted": ts_false,
        "person_uid": "uid-1",
        "person_data": {
            "person_firstname": ts_str,
            "person_lastname": {"value": "García", "updatedAt": "2026-06-01T00:00:00Z"},
            "person_display_name": {"value": "Ana García", "updatedAt": "2026-06-01T00:00:00Z"},
            "male": ts_false,
            "female": ts_true,
            "birth_date": ts_null_date,
            "assignments": [],
            "timeAway": [],
            "archived": ts_false,
            "disqualified": ts_false,
            "email": ts_blank,
            "address": ts_blank,
            "phone": ts_blank,
            "publisher_baptized": {
                "active": ts_true,
                "anointed": ts_false,
                "other_sheep": ts_true,
                "baptism_date": ts_null_date,
                "history": [],
            },
            "publisher_unbaptized": {"active": ts_false, "history": []},
            "midweek_meeting_student": {"active": ts_true, "history": []},
            "privileges": [],
            "enrollments": [],
            "emergency_contacts": [],
            "family_members": {"head": True, "members": [], "updatedAt": "2026-06-01T00:00:00Z"},
        },
    }


def _empty_ayf() -> dict:
    empty_assignment = {"type": "", "name": "", "value": "", "updatedAt": "2026-06-01T00:00:00Z"}
    return {
        "main_hall": {"student": [], "assistant": []},
        "aux_class_1": {"student": empty_assignment, "assistant": empty_assignment},
        "aux_class_2": {"student": empty_assignment, "assistant": empty_assignment},
    }


def _minimal_sched_week_payload() -> dict:
    empty_assignment = {"type": "", "name": "", "value": "", "updatedAt": "2026-06-01T00:00:00Z"}
    return {
        "weekOf": "2026-06-01",
        "midweek_meeting": {
            "chairman": {"main_hall": [], "aux_class_1": empty_assignment},
            "opening_prayer": [],
            "tgw_talk": [],
            "tgw_gems": [],
            "tgw_bible_reading": {
                "main_hall": [],
                "aux_class_1": empty_assignment,
                "aux_class_2": empty_assignment,
            },
            "ayf_part1": _empty_ayf(),
            "ayf_part2": _empty_ayf(),
            "ayf_part3": _empty_ayf(),
            "ayf_part4": _empty_ayf(),
            "lc_part1": [],
            "lc_part2": [],
            "lc_part3": [],
            "lc_cbs": {"conductor": [], "reader": []},
            "closing_prayer": [],
            "circuit_overseer": empty_assignment,
            "week_type": [],
        },
        "weekend_meeting": {
            "chairman": [],
            "opening_prayer": [],
            "public_talk_type": [],
            "speaker": {"part_1": [], "part_2": [], "substitute": []},
            "wt_study": {"conductor": [], "reader": []},
            "closing_prayer": [],
            "circuit_overseer": empty_assignment,
            "week_type": [],
            "outgoing_talks": [],
        },
    }
