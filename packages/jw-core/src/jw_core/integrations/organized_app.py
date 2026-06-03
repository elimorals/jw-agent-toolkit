"""F54.5 — read/write organized-app backup files.

organized-app (sws2apps, MIT) is the React PWA used by hundreds of
congregations. It exports its state as a JSON file:

    {
      "name": "...",
      "exported": "2026-06-02T...Z",
      "version": "3.37.1",
      "data": {
        "persons":      { "<uid>": <PersonType>, ... },
        "sched":        { "<weekOf>": <SchedWeekType>, ... },
        "meeting_attendance": [ <MeetingAttendanceType>, ... ],
        "field_service_groups": [ <FieldServiceGroupType>, ... ],
        "user_field_service_reports": [ <UserFieldServiceMonthlyReportType>, ... ],
        ...
      }
    }

This module is the bridge between that JSON shape and our Pydantic models in
`jw_core.models_organized`. Each top-level helper is small and orthogonal so
agents can import-export individual collections rather than the whole envelope.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Final

from pydantic import BaseModel, ConfigDict

from jw_core.models_organized.field_service_groups import FieldServiceGroupType
from jw_core.models_organized.field_service_report import (
    UserFieldServiceMonthlyReportType,
)
from jw_core.models_organized.meeting_attendance import MeetingAttendanceType
from jw_core.models_organized.person import PersonType
from jw_core.models_organized.schedule import SchedWeekType

DEFAULT_VERSION: Final = "3.37.0"


class OrganizedBackup(BaseModel):
    """The full envelope an organized-app export produces."""

    model_config = ConfigDict(populate_by_name=True)

    name: str
    exported: str
    version: str
    persons: list[PersonType] = []
    schedules: list[SchedWeekType] = []
    meeting_attendance: list[MeetingAttendanceType] = []
    field_service_groups: list[FieldServiceGroupType] = []
    user_field_service_reports: list[UserFieldServiceMonthlyReportType] = []


class OrganizedBackupError(RuntimeError):
    pass


# ── Reading ─────────────────────────────────────────────────────────────


def parse_organized_backup(path: Path | str) -> OrganizedBackup:
    """Load an organized-app `.backup` JSON file into typed models.

    The file's `data` block uses indexed dicts (`persons["uid"] = …`) for
    some tables and lists for others. We normalize both into lists keyed
    by the model's intrinsic id (person_uid, weekOf, group_id, …).
    """
    src = Path(path)
    try:
        raw = json.loads(src.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise OrganizedBackupError(f"{src}: not a valid backup ({exc})") from exc
    return _build_from_raw(raw)


def parse_organized_backup_dict(raw: dict) -> OrganizedBackup:
    """Same as `parse_organized_backup` but from an in-memory dict.

    Used by tests + by agents that already have the JSON parsed.
    """
    return _build_from_raw(raw)


def _build_from_raw(raw: dict) -> OrganizedBackup:
    data = raw.get("data", {}) or {}
    return OrganizedBackup(
        name=raw.get("name", ""),
        exported=raw.get("exported", ""),
        version=raw.get("version", ""),
        persons=_load_collection(data.get("persons"), PersonType),
        schedules=_load_collection(data.get("sched"), SchedWeekType),
        meeting_attendance=_load_collection(data.get("meeting_attendance"), MeetingAttendanceType),
        field_service_groups=_load_collection(data.get("field_service_groups"), FieldServiceGroupType),
        user_field_service_reports=_load_collection(
            data.get("user_field_service_reports"), UserFieldServiceMonthlyReportType
        ),
    )


def _load_collection(payload: object, model_cls: type[BaseModel]) -> list:  # type: ignore[type-arg]
    """Normalize organized-app's mixed dict-or-list collections to a list."""
    if payload is None:
        return []
    if isinstance(payload, list):
        return [model_cls.model_validate(item) for item in payload]
    if isinstance(payload, dict):
        out = []
        for item in payload.values():
            try:
                out.append(model_cls.model_validate(item))
            except Exception:  # noqa: BLE001 - skip a single malformed row
                continue
        return out
    return []


# ── Writing ─────────────────────────────────────────────────────────────


def write_organized_backup(
    path: Path | str,
    backup: OrganizedBackup,
    *,
    indent: int | None = 2,
) -> Path:
    """Serialize an `OrganizedBackup` to disk as JSON.

    organized-app expects `data.persons` as an object keyed by `person_uid`,
    schedules keyed by `weekOf`. We reconstruct those indexed shapes here.
    """
    out_path = Path(path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(_to_envelope(backup), indent=indent), encoding="utf-8")
    return out_path


def _to_envelope(backup: OrganizedBackup) -> dict:
    return {
        "name": backup.name,
        "exported": backup.exported or datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "version": backup.version or DEFAULT_VERSION,
        "data": {
            "persons": {p.person_uid: p.model_dump(by_alias=True) for p in backup.persons},
            "sched": {s.weekOf: s.model_dump(by_alias=True) for s in backup.schedules},
            "meeting_attendance": [a.model_dump(by_alias=True) for a in backup.meeting_attendance],
            "field_service_groups": [g.model_dump(by_alias=True) for g in backup.field_service_groups],
            "user_field_service_reports": [r.model_dump(by_alias=True) for r in backup.user_field_service_reports],
        },
    }
