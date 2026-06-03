"""F54.5 — round-trip tests for organized-app backup IO."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from jw_core.integrations.organized_app import (
    OrganizedBackup,
    OrganizedBackupError,
    parse_organized_backup,
    parse_organized_backup_dict,
    write_organized_backup,
)


def _person_payload(uid: str, firstname: str) -> dict:
    ts_false = {"value": False, "updatedAt": "2026-06-01T00:00:00Z"}
    ts_true = {"value": True, "updatedAt": "2026-06-01T00:00:00Z"}
    ts_str = {"value": firstname, "updatedAt": "2026-06-01T00:00:00Z"}
    ts_blank = {"value": "", "updatedAt": "2026-06-01T00:00:00Z"}
    ts_null = {"value": None, "updatedAt": "2026-06-01T00:00:00Z"}
    return {
        "_deleted": ts_false,
        "person_uid": uid,
        "person_data": {
            "person_firstname": ts_str,
            "person_lastname": ts_blank,
            "person_display_name": ts_str,
            "male": ts_true,
            "female": ts_false,
            "birth_date": ts_null,
            "assignments": [],
            "timeAway": [],
            "archived": ts_false,
            "disqualified": ts_false,
            "email": ts_blank,
            "address": ts_blank,
            "phone": ts_blank,
            "publisher_baptized": {
                "active": ts_true, "anointed": ts_false, "other_sheep": ts_true,
                "baptism_date": ts_null, "history": [],
            },
            "publisher_unbaptized": {"active": ts_false, "history": []},
            "midweek_meeting_student": {"active": ts_true, "history": []},
            "privileges": [],
            "enrollments": [],
            "emergency_contacts": [],
            "family_members": {"head": True, "members": [], "updatedAt": "2026-06-01T00:00:00Z"},
        },
    }


def test_parse_dict_with_persons_indexed_by_uid() -> None:
    """organized-app stores persons as `{uid: PersonType}` — we accept that shape."""
    payload = {
        "name": "cong-backup",
        "exported": "2026-06-02T10:00:00Z",
        "version": "3.37.1",
        "data": {
            "persons": {
                "uid-1": _person_payload("uid-1", "Ana"),
                "uid-2": _person_payload("uid-2", "Bruno"),
            }
        },
    }
    backup = parse_organized_backup_dict(payload)
    assert backup.name == "cong-backup"
    assert len(backup.persons) == 2
    uids = sorted(p.person_uid for p in backup.persons)
    assert uids == ["uid-1", "uid-2"]


def test_parse_dict_with_lists_works_too() -> None:
    """Some tables (meeting_attendance, FSG) are lists, not indexed dicts."""
    payload = {
        "name": "x", "exported": "2026-06-02T10:00:00Z", "version": "3.37.1",
        "data": {
            "field_service_groups": [
                {
                    "group_id": "g-1",
                    "group_data": {
                        "deleted": False,
                        "updatedAt": "2026-06-01T00:00:00Z",
                        "name": "Grupo A", "sort_index": 0, "members": [],
                    },
                },
            ],
        },
    }
    backup = parse_organized_backup_dict(payload)
    assert len(backup.field_service_groups) == 1
    assert backup.field_service_groups[0].group_data.name == "Grupo A"


def test_parse_skips_malformed_rows() -> None:
    """A single corrupt person dict doesn't kill the whole backup."""
    payload = {
        "name": "x", "exported": "2026-06-02T10:00:00Z", "version": "3.37.1",
        "data": {
            "persons": {
                "uid-1": _person_payload("uid-1", "Ana"),
                "uid-bad": {"garbage": True},
            }
        },
    }
    backup = parse_organized_backup_dict(payload)
    assert [p.person_uid for p in backup.persons] == ["uid-1"]


def test_round_trip_file(tmp_path: Path) -> None:
    """Read → re-serialize → re-read produces equivalent data."""
    payload = {
        "name": "cong", "exported": "2026-06-02T10:00:00Z", "version": "3.37.1",
        "data": {"persons": {"uid-1": _person_payload("uid-1", "Ana")}},
    }
    src = tmp_path / "backup.json"
    src.write_text(json.dumps(payload))

    backup = parse_organized_backup(src)
    out = tmp_path / "round.json"
    write_organized_backup(out, backup)

    back2 = parse_organized_backup(out)
    assert back2.name == "cong"
    assert back2.persons[0].person_data.person_firstname.value == "Ana"


def test_write_normalizes_to_indexed_dicts(tmp_path: Path) -> None:
    """Output `data.persons` must be keyed by `person_uid` (organized-app shape)."""
    backup = OrganizedBackup(
        name="x",
        exported="2026-06-02T10:00:00Z",
        version="3.37.1",
        persons=[_build_typed_person("uid-X")],
    )
    out = tmp_path / "out.json"
    write_organized_backup(out, backup)

    raw = json.loads(out.read_text())
    assert isinstance(raw["data"]["persons"], dict)
    assert "uid-X" in raw["data"]["persons"]


def test_parse_invalid_file_raises(tmp_path: Path) -> None:
    bad = tmp_path / "bad.json"
    bad.write_text("not json")
    with pytest.raises(OrganizedBackupError):
        parse_organized_backup(bad)


def _build_typed_person(uid: str) -> "PersonType":  # type: ignore[name-defined]
    from jw_core.models_organized.person import PersonType

    return PersonType.model_validate(_person_payload(uid, "Ana"))
