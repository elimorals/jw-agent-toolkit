from __future__ import annotations

import pytest
from pydantic import ValidationError

from jw_agents.study_progress import (
    GoalKind,
    LessonRow,
    LessonStatus,
    StudentGoal,
)


def test_lesson_status_enum_values() -> None:
    assert LessonStatus.NOT_STARTED.value == "not_started"
    assert LessonStatus.IN_PROGRESS.value == "in_progress"
    assert LessonStatus.COMPLETED.value == "completed"
    assert LessonStatus.SKIPPED.value == "skipped"


def test_goal_kind_enum_includes_taxonomy() -> None:
    assert GoalKind.ATTEND_MEETINGS in GoalKind
    assert GoalKind.DROP_ADDICTION_SMOKING in GoalKind
    assert GoalKind.DROP_ADDICTION_ALCOHOL in GoalKind
    assert GoalKind.PRAY_DAILY in GoalKind
    assert GoalKind.FAMILY_WORSHIP in GoalKind
    assert GoalKind.BAPTISM in GoalKind


def test_lesson_row_validates_student_id() -> None:
    LessonRow(
        student_id="amelia2024",
        book_pub="lff",
        lesson=1,
        updated_at_iso="2026-05-30T00:00:00",
    )


def test_lesson_row_rejects_invalid_student_id() -> None:
    with pytest.raises(ValidationError):
        LessonRow(
            student_id="Amelia García",
            book_pub="lff",
            lesson=1,
            updated_at_iso="2026-05-30T00:00:00",
        )


def test_lesson_row_default_status_not_started() -> None:
    row = LessonRow(
        student_id="x_y_z",
        book_pub="lff",
        lesson=1,
        updated_at_iso="2026-05-30T00:00:00",
    )
    assert row.status == LessonStatus.NOT_STARTED


def test_student_goal_minimal() -> None:
    g = StudentGoal(kind=GoalKind.BAPTISM, set_at_iso="2026-05-30T00:00:00")
    assert g.kind == GoalKind.BAPTISM
    assert g.achieved_at_iso is None


# --- Task 5: salt + passphrase --------------------------------------------

from pathlib import Path

from jw_agents.study_progress import (
    PrivacyState,
    derive_encryptor_for_passphrase,
    load_or_create_salt,
)


def test_load_or_create_salt_creates_when_missing(tmp_path: Path) -> None:
    target = tmp_path / "salt.bin"
    state = load_or_create_salt(target)
    assert state == PrivacyState.CREATED
    assert target.exists()
    assert len(target.read_bytes()) == 16


def test_load_or_create_salt_returns_existing(tmp_path: Path) -> None:
    target = tmp_path / "salt.bin"
    load_or_create_salt(target)
    state2 = load_or_create_salt(target)
    assert state2 == PrivacyState.LOADED


def test_derive_encryptor_round_trip(tmp_path: Path) -> None:
    salt_path = tmp_path / "salt.bin"
    load_or_create_salt(salt_path)
    enc = derive_encryptor_for_passphrase("hunter2", salt_path=salt_path)
    assert enc.enabled
    token = enc.encrypt("nota sensible")
    assert enc.decrypt(token) == "nota sensible"
