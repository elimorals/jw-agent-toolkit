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
